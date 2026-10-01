"""Chart and text summary."""

import json
import re
import struct
from pathlib import Path

import pytest

from forecast import outputs
from forecast.outputs import text_summary, write_artifacts
from forecast.pipeline import run_forecast
from forecast.schema import RunResult
from tests import synthetic

pytestmark = pytest.mark.slow
EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
NAMES = ("retail_sales", "saas_revenue", "website_traffic", "inventory_demand")


@pytest.fixture(scope="module")
def written(tmp_path_factory):
    """Each example run once and written to disk."""
    root = tmp_path_factory.mktemp("outputs")
    out = {}
    for name in NAMES:
        outcome = run_forecast(EXAMPLES / f"{name}.csv")
        out[name] = (outcome, write_artifacts(outcome, root / name), root / name)
    return out


def png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return struct.unpack(">II", data[16:24])  # width, height from the IHDR chunk


# ------------------------------------------------------------ chart


def test_a_chart_is_produced_for_every_example(written):
    for name, (_, result, directory) in written.items():
        png = directory / "forecast.png"
        width, height = png_size(png)
        assert result.artifacts.plot == "forecast.png", name
        assert width >= 1500 and height >= 700 and png.stat().st_size > 20_000, name


def test_the_run_directory_now_has_five_files(written):
    for _, _, directory in written.values():
        assert sorted(p.name for p in directory.iterdir()) == [
            "backtest.csv", "forecast.csv", "forecast.png", "profile.json", "result.json",
        ]  # fmt: skip


def test_written_result_json_matches_the_returned_result(written):
    for _, result, directory in written.values():
        assert RunResult.model_validate_json((directory / "result.json").read_text()) == result


def test_chart_failure_never_loses_the_forecast(monkeypatch, tmp_path):
    def boom(*_args, **_kwargs):
        raise RuntimeError("no display")

    monkeypatch.setattr("forecast.plot.plot_forecast", boom)
    outcome = run_forecast(EXAMPLES / "saas_revenue.csv")
    result = write_artifacts(outcome, tmp_path / "run")
    assert result.artifacts.plot is None and result.status == "ok_with_warnings"
    assert "PLOT_FAILED" in {w.code for w in result.warnings}
    assert (tmp_path / "run" / "forecast.csv").exists() and (
        tmp_path / "run" / "result.json"
    ).exists()
    assert not (tmp_path / "run" / "forecast.png").exists()
    assert RunResult.model_validate_json((tmp_path / "run" / "result.json").read_text()) == result


def test_chart_handles_filled_gaps_and_negative_values(tmp_path):
    df = synthetic.with_missing_values(synthetic.white_noise(level=0.0, noise=5.0), [40, 41, 90])
    csv = tmp_path / "d.csv"
    df.to_csv(csv, index=False)
    outcome = run_forecast(csv, horizon=14)
    write_artifacts(outcome, tmp_path / "run")
    assert png_size(tmp_path / "run" / "forecast.png")[0] >= 1500


# ------------------------------------------------------------ text summary

NUMBER = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?%?")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def json_numbers(node):
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        yield float(node)
    elif isinstance(node, dict):
        for v in node.values():
            yield from json_numbers(v)
    elif isinstance(node, list):
        for v in node:
            yield from json_numbers(v)


def explained(token, numbers):
    """True if some number in result.json prints as `token` at the precision shown.

    A percent token may come from a fraction (0.16 -> 16%) or from a value already in percent
    units (sMAPE 3.7 -> 3.7%).
    """
    percent = token.endswith("%")
    text = token.rstrip("%").replace(",", "").lstrip("+")
    shown = abs(float(text))
    decimals = len(text.split(".")[1]) if "." in text else 0
    tol = 0.5 * 10**-decimals + 1e-9
    scales = (1.0, 100.0) if percent else (1.0,)
    return any(abs(abs(v) * k - shown) <= tol for v in numbers for k in scales)


def test_every_number_in_the_summary_comes_from_result_json(written):
    for name, (_, result, _) in written.items():
        text = text_summary(result)
        numbers = list(json_numbers(json.loads(result.model_dump_json())))
        body = [ln for ln in text.splitlines() if not ln.startswith(("  [", "Files:"))]
        unexplained = [
            tok
            for ln in body
            for tok in NUMBER.findall(DATE.sub("", ln))
            if not explained(tok, numbers)
        ]
        assert unexplained == [], f"{name}: numbers not found in result.json: {unexplained}"


def test_summary_warnings_are_the_result_warnings_verbatim(written):
    for name, (_, result, _) in written.items():
        text = text_summary(result)
        for w in result.warnings:
            if w.severity == "warn":
                assert f"[{w.code}] {w.message}" in text, name
            else:
                assert w.message not in text, name  # info notices stay in result.json


def test_summary_states_model_pattern_and_uncertainty(written):
    text = text_summary(written["retail_sales"][1])
    assert text.startswith("FORECAST ANALYSIS: sales")
    for label in (
        "Horizon",
        "Pattern",
        "Model",
        "Why",
        "Backtest",
        "Sum of forecasts",
        "Uncertainty",
        "Intervals",
    ):
        assert label in text
    assert "weekly seasonality (period 7" in text and "upward trend" in text
    assert "AutoETS" in text and "5% a complex model must clear" in text


def test_summary_names_the_pattern_without_claiming_causes(written):
    texts = {n: text_summary(r) for n, (_, r, _) in written.items()}
    assert (
        "intermittent demand" in texts["inventory_demand"]
        and "no significant seasonality" in texts["inventory_demand"]
    )
    assert "yearly" not in texts["retail_sales"]
    for text in texts.values():
        assert not re.search(
            r"\b(because|due to|caused|driven by)\b", text.replace("because the", ""), re.IGNORECASE
        )


def test_summary_marks_a_fallback_model(written):
    _, result, _ = written["retail_sales"]
    fallback = result.model_copy(
        update={"forecast": result.forecast.model_copy(update={"model": "Naive"})}
    )
    assert "Naive (fallback; AutoETS was selected)" in text_summary(fallback)


def test_summary_reports_calibration(written):
    result = written["saas_revenue"][1]
    assert result.intervals.method == "calibrated"
    text = text_summary(result)
    assert "calibrated" in text and f"widened x{result.intervals.factor_80:.2f}" in text


def test_cli_text_is_the_summary(written, capsys, tmp_path):
    from forecast.cli import main

    code = main([str(EXAMPLES / "inventory_demand.csv"), "--output", str(tmp_path / "o")])
    out = capsys.readouterr().out
    assert code == 0 and out.startswith("FORECAST ANALYSIS: units") and "Files:" in out
    assert (tmp_path / "o" / "forecast.png").exists()


def test_module_exports():
    assert callable(outputs.text_summary) and callable(outputs.write_artifacts)
