"""The skill is documentation the model follows, so it is tested like code: valid, complete, in sync."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from forecast.diagnostics import WARNING_CODES
from forecast.schema import RefusalReport
from forecast.selection import MARGIN

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "forecast"
SKILL = (SKILL_DIR / "SKILL.md").read_text()
INTERPRETATION = (SKILL_DIR / "references" / "interpretation.md").read_text()
SELECTION = (SKILL_DIR / "references" / "model-selection.md").read_text()


def frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md must start with YAML frontmatter"
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip('"')
    return fields


def test_frontmatter_has_the_fields_claude_code_reads():
    fm = frontmatter(SKILL)
    assert len(fm["description"]) > 60 and "forecast" in fm["description"].lower()
    assert fm["argument-hint"].startswith("<file.csv>")
    assert "${CLAUDE_PLUGIN_ROOT}/bin/forecast" in fm["allowed-tools"]
    assert (
        fm["description"].count("\n") == 0 and len(fm["description"]) < 1536
    )  # skill listing limit


def test_skill_always_calls_the_engine_by_its_plugin_path():
    assert "${CLAUDE_PLUGIN_ROOT}/bin/forecast run" in SKILL
    # a bare `forecast ...` command would not be on PATH
    assert not re.search(r"^\s*forecast (run|profile)\b", SKILL, re.MULTILINE)


def test_skill_covers_every_exit_code_and_flag_the_engine_has():
    for code in ("| 0 |", "| 3 |", "| 4 |", "| 127 |"):
        assert code in SKILL
    for flag in ("--horizon", "--target", "--date", "--where", "--agg", "--fill", "--date-order"):
        assert flag in SKILL, flag


def test_skill_states_the_separation_of_responsibilities():
    for rule in ("Never compute statistics", "Never choose or override the model", "Never open the user's data file",
                 "Never invent a cause", "Never present a forecast as more reliable"):  # fmt: skip
        assert rule in SKILL
    assert "ask, never guess" in SKILL.lower()


def test_skill_forbids_decorating_the_command_which_would_defeat_the_allowed_tools_pattern():
    assert "nothing added" in SKILL and "`2>&1`" in SKILL and "`; echo $?`" in SKILL


def test_skill_has_a_self_check_covering_the_slips_seen_in_live_runs():
    assert "check your own answer" in SKILL.lower()
    for slip in (
        "Do\n  not derive new ones",
        "No causal language about the data",
        "Speculation lives in one place",
    ):
        assert slip in SKILL


def test_skill_reads_results_with_the_read_tool_not_shell_scripts():
    assert "**with the Read\ntool, not with shell scripts**" in SKILL
    assert re.search(r"allowed-tools:.*\bRead\b", SKILL)


def test_referenced_files_exist():
    for ref in re.findall(r"`(references/[a-z-]+\.md)`", SKILL):
        assert (SKILL_DIR / ref).is_file(), ref


def test_interpretation_reference_covers_every_warning_code():
    missing = [c for c in WARNING_CODES if f"`{c}`" not in INTERPRETATION]
    assert missing == [], f"warning codes with no plain-language guidance: {missing}"


def test_interpretation_reference_covers_every_refusal_code():
    from typing import get_args

    codes = get_args(RefusalReport.model_fields["code"].annotation)
    missing = [c for c in codes if f"`{c}`" not in INTERPRETATION]
    assert missing == [], f"refusal codes with no guidance: {missing}"


def test_model_selection_reference_matches_the_engine():
    assert f"{MARGIN:.0%}" in SELECTION
    from forecast.models import REGISTRY
    from forecast.selection import select_model  # noqa: F401 - the rule lives there

    for spec in REGISTRY:
        assert spec.name in SELECTION, spec.name
    for reason in (
        "beat_baseline_by_margin",
        "baseline_within_margin",
        "baseline_best",
        "only_baselines_ran",
        "no_baseline_ran",
    ):
        assert f"`{reason}`" in SELECTION
    from forecast.backtest import MAX_WINDOWS, MIN_WINDOWS

    assert f"{MIN_WINDOWS} to {MAX_WINDOWS} windows" in SELECTION
    from forecast.intervals import CALIBRATE_BELOW

    assert f"under {CALIBRATE_BELOW:.0%}" in SELECTION


def test_every_exit_code_in_the_skill_matches_the_cli():
    from forecast.cli import EXIT_NEEDS_INPUT, EXIT_REFUSED

    assert (EXIT_NEEDS_INPUT, EXIT_REFUSED) == (3, 4)


def test_plugin_manifests_are_consistent():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert plugin["name"] == "forecast" and market["plugins"][0]["name"] == plugin["name"]
    assert market["plugins"][0]["source"] == "./"
    assert (ROOT / "bin" / "forecast").stat().st_mode & 0o111, "bin/forecast must be executable"


@pytest.mark.skipif(shutil.which("claude") is None, reason="claude CLI not installed")
def test_claude_plugin_validate_passes():
    run = subprocess.run(
        ["claude", "plugin", "validate", str(ROOT)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
