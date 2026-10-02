"""The HTML dashboard: complete, safe, theme-aware, and showing only the engine's numbers."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from forecast.outputs import _num, write_artifacts
from forecast.pipeline import run_forecast
from forecast.schema import RunResult
from tests import synthetic

pytestmark = pytest.mark.slow
EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
NAMES = ("retail_sales", "saas_revenue", "website_traffic", "inventory_demand")


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    root = tmp_path_factory.mktemp("dash")
    out = {}
    for name in NAMES:
        outcome = run_forecast(EXAMPLES / f"{name}.csv")
        result = write_artifacts(outcome, root / name)
        out[name] = (outcome, result, (root / name / "dashboard.html").read_text(encoding="utf-8"))
    return out


def payload(page):
    m = re.search(r'<script type="application/json" id="dash-data">(.*?)</script>', page, re.DOTALL)
    assert m, "no embedded data"
    return json.loads(m.group(1))


def script(page):
    return re.findall(r"<script>(.*?)</script>", page, re.DOTALL)[-1]


# ------------------------------------------------------------ contract


def test_dashboard_is_written_and_recorded(pages):
    for name, (_, result, page) in pages.items():
        assert result.artifacts.dashboard == "dashboard.html", name
        assert page.startswith("<!doctype html>") and len(page) < 200_000, name
        assert RunResult.model_validate_json(result.model_dump_json()) == result


def test_title_is_a_short_name(pages):
    for name, (outcome, _, page) in pages.items():
        title = re.search(r"<title>(.*?)</title>", page).group(1)
        target = outcome.result.input.target_column
        assert title == f"{target[:1].upper()}{target[1:]} Forecast" and len(title.split()) <= 4, (
            name
        )
        assert ":" not in title and "-" not in title


def test_page_is_self_contained_with_no_external_loads(pages):
    for name, (_, _, page) in pages.items():
        assert "<script src" not in page and "<link" not in page and "@import" not in page, name
        urls = set(re.findall(r"https?://[^\s\"')<>]+", page))
        assert urls <= {"http://www.w3.org/2000/svg"}, (name, urls)


def test_theme_tokens_cover_light_dark_and_the_explicit_toggle(pages):
    page = pages["retail_sales"][2]
    assert ":root {" in page and "--bg:" in page
    assert (
        "@media (prefers-color-scheme: dark)" in page and ':root:not([data-theme="light"])' in page
    )
    assert ':root[data-theme="dark"]' in page and page.count("color-scheme: dark") >= 2
    assert re.search(r"body \{[^}]*background: var\(--bg\)", page)
    assert 'name="viewport"' in page and "padding-inline: 16px" in page
    # no literal colours in component rules: every colour in the stylesheet sits in a token definition
    css = re.search(r"<style>(.*?)</style>", page, re.DOTALL).group(1)
    outside = re.sub(r"(:root[^{]*\{[^}]*\})", "", css)
    outside = re.sub(r"@media[^{]*\{\s*:root[^{]*\{[^}]*\}\s*\}", "", outside)
    literal = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", outside)
    assert literal == ["rgba("] or all(x == "rgba(" for x in literal)  # only the shadow


def test_script_parses(pages):
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    for name, (_, _, page) in pages.items():
        run = subprocess.run(
            ["node", "--check", "-"],
            input=script(page),
            capture_output=True,
            text=True,
            check=False,
        )
        assert run.returncode == 0, (name, run.stderr[:300])


# ------------------------------------------------------------ the numbers are the engine's


def test_headline_figures_are_the_engine_values(pages):
    for name, (_, result, page) in pages.items():
        f = result.forecast
        for text in (_num(f.total), _num(f.mean), f.model, _num(f.last.lo_80), _num(f.last.hi_80)):
            assert text in page, (name, text)
        if f.change_vs_prior is not None:
            assert f"{f.change_vs_prior:+.1%}" in page and _num(f.previous_total) in page


def test_embedded_series_equal_the_forecast_file(pages):
    for name, (outcome, _, page) in pages.items():
        d = payload(page)
        fc = outcome.forecast
        assert len(d["forecast"]["ds"]) == len(fc) == outcome.result.forecast.horizon, name
        for col in ("forecast", "lo_80", "hi_80", "lo_95", "hi_95"):
            assert d["forecast"][col] == [float(v) for v in fc[col]], (name, col)
        assert d["history"]["y"][-1] == pytest.approx(float(outcome.history["y"].iloc[-1]))
        assert d["selected"] == outcome.result.selection.winner


def test_models_and_warnings_match_the_result(pages):
    for name, (_, result, page) in pages.items():
        d = payload(page)
        ranked = [m.name for m in result.selection.ranking]
        assert [m["name"] for m in d["models"]] == ranked, name
        assert [w["code"] for w in d["warnings"]] == [w.code for w in result.warnings], name
        for m in d["models"]:
            assert len(m["windowMae"]) == result.backtest.plan.n_windows
        assert {x["name"] for x in d["excluded"]} == {
            m.name for m in result.backtest.models if m.status != "ok"
        }


def test_every_warning_is_visible_in_the_page_data(pages):
    for name, (_, result, page) in pages.items():
        msgs = {w["message"] for w in payload(page)["warnings"]}
        assert all(w.message in msgs for w in result.warnings), name


def test_no_placeholder_or_nan_leaks(pages):
    for name, (_, _, page) in pages.items():
        static = re.sub(r"<script.*?</script>", "", page, flags=re.DOTALL)
        static = re.sub(r"<style>.*?</style>", "", static, flags=re.DOTALL)
        for bad in ("__", "NaN", "undefined", "None", "inf"):
            assert bad not in static, (name, bad)


def test_calibrated_runs_say_so(pages):
    result, page = pages["saas_revenue"][1], pages["saas_revenue"][2]
    assert result.intervals.method == "calibrated" and "widened by" in page


# ------------------------------------------------------------ safety and limits


def test_hostile_column_names_cannot_break_out_or_be_re_substituted(tmp_path):
    df = synthetic.trend_seasonality(120).rename(
        columns={"value": "</script><img src=x onerror=alert(1)>__DATA__"}
    )
    csv = tmp_path / "evil.csv"
    df.to_csv(csv, index=False)
    outcome = run_forecast(csv, horizon=7)
    write_artifacts(outcome, tmp_path / "out")
    page = (tmp_path / "out" / "dashboard.html").read_text(encoding="utf-8")
    assert page.count('id="dash-data"') == 1
    assert "<img src=x" not in page and "</script><img" not in page
    assert payload(page)["target"].startswith("</script>")  # decoded back correctly from <
    static = re.sub(r"<script.*?</script>", "", page, flags=re.DOTALL)
    assert "&lt;/script&gt;" in static  # shown as text, escaped


def test_history_is_capped_and_the_page_says_so(tmp_path):
    n = 2000
    df = pd.DataFrame(
        {
            "date": pd.date_range("2018-01-01", periods=n),
            "value": synthetic.trend_seasonality(n)["value"],
        }
    )
    csv = tmp_path / "long.csv"
    df.to_csv(csv, index=False)
    outcome = run_forecast(csv, horizon=14)
    write_artifacts(outcome, tmp_path / "out")
    d = payload((tmp_path / "out" / "dashboard.html").read_text(encoding="utf-8"))
    assert len(d["history"]["y"]) == 1500 and d["totalHistory"] == n


def test_filled_periods_are_flagged_in_the_data(tmp_path):
    df = synthetic.with_missing_values(synthetic.trend_seasonality(150), [100, 101])
    csv = tmp_path / "gaps.csv"
    df.to_csv(csv, index=False)
    outcome = run_forecast(csv, horizon=7)
    write_artifacts(outcome, tmp_path / "out")
    page = (tmp_path / "out" / "dashboard.html").read_text(encoding="utf-8")
    assert payload(page)["history"]["imputed"] == [100, 101]
    assert "Filled periods" in page


def test_a_dashboard_failure_never_loses_the_forecast(monkeypatch, tmp_path):
    def boom(*_a, **_k):
        raise RuntimeError("template broke")

    monkeypatch.setattr("forecast.dashboard.render_dashboard", boom)
    outcome = run_forecast(EXAMPLES / "saas_revenue.csv")
    result = write_artifacts(outcome, tmp_path / "run")
    assert result.artifacts.dashboard is None and result.status == "ok_with_warnings"
    assert "DASHBOARD_FAILED" in {w.code for w in result.warnings}
    for name in ("forecast.csv", "result.json", "forecast.png"):
        assert (tmp_path / "run" / name).exists()
    assert not (tmp_path / "run" / "dashboard.html").exists()
