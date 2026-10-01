import json

import pytest

from forecast.cli import EXIT_NEEDS_INPUT, EXIT_OK, EXIT_REFUSED, main
from forecast.schema import NeedsInputReport, ProfileReport, RefusalReport
from tests import synthetic


@pytest.fixture
def csv(tmp_path):
    p = tmp_path / "sales.csv"
    synthetic.weekly_seasonality().rename(columns={"value": "sales"}).to_csv(p, index=False)
    return p


def run(capsys, *argv):
    code = main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def test_profile_ok(csv, capsys):
    code, out = run(capsys, "profile", str(csv))
    assert code == EXIT_OK and out["status"] == "ok"
    report = ProfileReport.model_validate(out)
    assert report.input.target_column == "sales" and report.seasonality.season_length == 7


def test_profile_writes_output_dir(csv, tmp_path, capsys):
    out_dir = tmp_path / "results"
    code, out = run(capsys, "profile", str(csv), "--output", str(out_dir))
    assert code == EXIT_OK
    assert json.loads((out_dir / "profile.json").read_text()) == out


def test_profile_needs_input_exit_3(tmp_path, capsys):
    p = tmp_path / "multi.csv"
    p.write_text(
        "date,store,sales\n"
        + "\n".join(f"2024-01-{d:02d},{s},{d}" for d in range(1, 21) for s in "AB")
    )
    code, out = run(capsys, "profile", str(p))
    assert code == EXIT_NEEDS_INPUT and out["status"] == "needs_input"
    assert NeedsInputReport.model_validate(out).ambiguities[0].kind == "series"


def test_profile_resolves_with_where_and_agg(tmp_path, capsys):
    p = tmp_path / "multi.csv"
    p.write_text(
        "date,store,sales\n"
        + "\n".join(f"2024-01-{d:02d},{s},{d}" for d in range(1, 21) for s in "AB")
    )
    code, out = run(capsys, "profile", str(p), "--where", "store=A")
    assert code == EXIT_OK and out["input"]["where"] == {"store": "A"}
    code, out = run(capsys, "profile", str(p), "--agg", "sum")
    assert code == EXIT_OK and out["stats"]["mean"] == pytest.approx(2 * 10.5)


def test_profile_refused_exit_4(tmp_path, capsys):
    code, out = run(capsys, "profile", str(tmp_path / "missing.csv"))
    assert code == EXIT_REFUSED and RefusalReport.model_validate(out).code == "FILE_UNREADABLE"


def test_bad_where_is_usage_error(csv, capsys):
    with pytest.raises(SystemExit) as e:
        main(["profile", str(csv), "--where", "nonsense"])
    assert e.value.code == 2


def test_no_command_is_usage_error():
    with pytest.raises(SystemExit) as e:
        main([])
    assert e.value.code == 2


# ------------------------------------------------------------ run


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    """One real `forecast run --json` shared by the assertions below."""
    root = tmp_path_factory.mktemp("run")
    csv = root / "sales.csv"
    synthetic.trend_seasonality(300).rename(columns={"value": "sales"}).to_csv(csv, index=False)
    out = root / "results"
    return csv, out


def test_run_json_writes_artifacts_and_prints_a_valid_result(run_dir, capsys):
    from forecast.schema import RunResult

    csv, out = run_dir
    code = main(["run", str(csv), "--horizon", "21", "--json", "--output", str(out)])
    printed = json.loads(capsys.readouterr().out)
    assert code == EXIT_OK
    result = RunResult.model_validate(printed)
    assert result.forecast.horizon == 21 and result.artifacts.directory == str(out.resolve())
    assert sorted(p.name for p in out.iterdir()) == [
        "backtest.csv",
        "forecast.csv",
        "forecast.png",
        "profile.json",
        "result.json",
    ]
    assert json.loads((out / "result.json").read_text()) == printed


def test_bare_file_argument_means_run(run_dir, capsys, tmp_path):
    csv, _ = run_dir
    code = main([str(csv), "--horizon", "7", "--output", str(tmp_path / "o")])
    text = capsys.readouterr().out
    assert code == EXIT_OK and "FORECAST ANALYSIS: sales" in text and "7 daily periods" in text
    assert "Sum of forecasts" in text and (tmp_path / "o" / "forecast.csv").exists()


def test_flags_may_precede_the_file(run_dir, capsys, tmp_path):
    csv, _ = run_dir
    assert main(["--horizon", "7", str(csv), "--output", str(tmp_path / "o2")]) == EXIT_OK
    capsys.readouterr()


def test_run_needs_input_text_and_json(tmp_path, capsys):
    p = tmp_path / "multi.csv"
    p.write_text(
        "date,store,sales\n"
        + "\n".join(f"2024-01-{d:02d},{s},{d}" for d in range(1, 21) for s in "AB")
    )
    assert main(["run", str(p)]) == EXIT_NEEDS_INPUT
    text = capsys.readouterr().out
    assert "Which one should be forecast?" in text and "--where store=<value>" in text
    assert "values: A, B" in text  # the caller needs the valid values to build --where
    assert main(["run", str(p), "--json"]) == EXIT_NEEDS_INPUT
    assert json.loads(capsys.readouterr().out)["status"] == "needs_input"


def test_run_refused_text_and_json(tmp_path, capsys):
    p = tmp_path / "flat.csv"
    synthetic.constant().to_csv(p, index=False)
    assert main(["run", str(p)]) == EXIT_REFUSED
    assert "CONSTANT_SERIES" in capsys.readouterr().out
    assert main(["run", str(p), "--json"]) == EXIT_REFUSED
    assert json.loads(capsys.readouterr().out)["code"] == "CONSTANT_SERIES"


def test_run_usage_errors():
    for bad in (["run", "x.csv", "--horizon", "abc"], ["run"], ["run", "x.csv", "--agg", "median"]):
        with pytest.raises(SystemExit) as e:
            main(bad)
        assert e.value.code == 2
