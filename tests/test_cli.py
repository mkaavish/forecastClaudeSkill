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
