"""Live evaluation of the /forecast skill through Claude Code (costs model calls; not run in CI).

    python evals/run_skill_evals.py [scenario ...]

Each scenario runs `claude -p` with this repository loaded as a plugin, then checks
behaviour that must hold: the engine is called by its plugin path, the raw data are never
read, ambiguities are asked rather than guessed, refusals are explained, and every number in
the answer appears in result.json. Requires the `claude` CLI and `uv` on PATH.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
EXAMPLES = ROOT / "examples"

NUMBER = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?%?")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
CAUSAL = re.compile(r"\b(because|due to|caused by|driven by|as a result of)\b", re.IGNORECASE)


@dataclass
class Transcript:
    final_text: str = ""
    bash: list[str] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)  # AskUserQuestion payloads
    error: str = ""


def run_claude(prompt: str, cwd: Path, max_turns: int = 12) -> Transcript:
    cmd = ["claude", "-p", "--plugin-dir", str(ROOT), "--output-format", "stream-json", "--verbose",
           "--max-turns", str(max_turns), "--permission-mode", "acceptEdits", prompt]  # fmt: skip
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=900,
        check=False,
    )
    t = Transcript()
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "assistant":
            for block in event["message"]["content"]:
                if block.get("type") == "text":
                    t.final_text = block["text"]
                elif block.get("type") == "tool_use":
                    inp = block["input"]
                    if block["name"] == "Bash":
                        t.bash.append(inp.get("command", ""))
                    elif block["name"] == "Read":
                        t.reads.append(inp.get("file_path", ""))
                    elif block["name"] == "AskUserQuestion":
                        t.questions.append(json.dumps(inp))
    if proc.returncode not in (0, None) and not t.final_text:
        t.error = proc.stderr[-500:]
    return t


def json_numbers(node):
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        yield float(node)
    elif isinstance(node, str):
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", node)  # dates: prose may say "January 2026"
        if m:
            yield from (float(g) for g in m.groups())
    elif isinstance(node, dict):
        for v in node.values():
            yield from json_numbers(v)
    elif isinstance(node, list):
        for v in node:
            yield from json_numbers(v)


def unexplained_numbers(answer: str, result: dict) -> list[str]:
    """Numbers in the answer that do not appear in result.json at the precision shown."""
    numbers = list(json_numbers(result))
    bad = []
    for line in answer.splitlines():
        line = re.sub(r"^\s*(?:[-*>#]+|\d+[.)])\s*", "", line)  # list markers and headings
        line = DATE.sub("", re.sub(r"`[^`]*`|\(?https?://\S+", "", line))
        for tok in NUMBER.findall(line):
            percent = tok.endswith("%")
            text = tok.rstrip("%").replace(",", "").lstrip("+-")
            if not text or text.startswith("."):
                continue
            shown = float(text)
            decimals = len(text.split(".")[1]) if "." in text else 0
            tol = 0.5 * 10**-decimals + 1e-9
            scales = (1.0, 100.0) if percent else (1.0,)
            if not any(abs(abs(v) * k - shown) <= tol for v in numbers for k in scales):
                bad.append(tok)
    return bad


def load_result(cwd: Path, name: str) -> dict:
    return json.loads((cwd / "forecast-output" / name / "result.json").read_text())


# --------------------------------------------------------------------------- scenarios


@dataclass
class Check:
    ok: bool
    what: str


ANSWERS: dict[str, str] = {}  # scenario name -> final answer, printed when a check fails


def engine_calls(t: Transcript) -> list[str]:
    return [c for c in t.bash if "bin/forecast" in c]


def scenario_forecast(cwd: Path) -> list[Check]:
    shutil.copy(EXAMPLES / "retail_sales.csv", cwd)
    t = run_claude("/forecast:forecast retail_sales.csv --horizon 30", cwd)
    ANSWERS["forecast"] = t.final_text
    calls = engine_calls(t)
    result = (
        load_result(cwd, "retail_sales")
        if (cwd / "forecast-output" / "retail_sales" / "result.json").exists()
        else None
    )
    checks = [
        Check(
            bool(calls) and "bin/forecast run" in calls[0], "calls the engine by its plugin path"
        ),
        Check(not any("retail_sales.csv" in r for r in t.reads), "never reads the raw data file"),
        Check(result is not None, "a result was produced"),
    ]
    if result:
        bad = unexplained_numbers(t.final_text, result)
        checks += [
            Check(not bad, f"every number in the answer is in result.json (unexplained: {bad})"),
            Check(result["forecast"]["model"] in t.final_text, "names the selected model"),
            Check("80%" in t.final_text, "states the 80% interval"),
            Check(
                any(w["code"] == "OUTLIERS" for w in result["warnings"])
                and re.search(r"outlier|unusual", t.final_text, re.IGNORECASE) is not None,
                "passes the outlier warning on in plain words",
            ),
            Check(CAUSAL.search(t.final_text) is None, "makes no causal claims"),
            Check(
                "forecast.png" in t.final_text or "chart" in t.final_text.lower(),
                "points to the chart",
            ),
        ]
    return checks


def scenario_ambiguous(cwd: Path) -> list[Check]:
    shutil.copy(EXAMPLES / "multi_store_sales.csv", cwd)
    t = run_claude("/forecast:forecast multi_store_sales.csv", cwd)
    ANSWERS["ambiguous"] = t.final_text
    asked = bool(t.questions) or (
        ("store" in t.final_text.lower())
        and ("product" in t.final_text.lower())
        and "?" in t.final_text
    )
    guessed = any(re.search(r"--(agg|where)", c) for c in engine_calls(t))
    return [
        Check(asked, "asks the user which series to forecast"),
        Check(not guessed, "does not pick --agg/--where on its own"),
        Check(
            not (cwd / "forecast-output").exists()
            or not any((cwd / "forecast-output").glob("*/result.json")),
            "produced no forecast before the answer",
        ),
    ]


def scenario_natural_language(cwd: Path) -> list[Check]:
    shutil.copy(EXAMPLES / "multi_store_sales.csv", cwd)
    t = run_claude(
        "/forecast:forecast multi_store_sales.csv total units sold across all stores and products, next 14 days",
        cwd,
    )
    ANSWERS["natural_language"] = t.final_text
    calls = " ".join(engine_calls(t))
    out = cwd / "forecast-output" / "multi_store_sales" / "result.json"
    checks = [
        Check(
            "--agg sum" in calls and "--horizon 14" in calls,
            "maps the request to --agg sum and --horizon 14",
        ),
        Check(out.exists(), "a result was produced without a needless question"),
    ]
    if out.exists():
        bad = unexplained_numbers(t.final_text, json.loads(out.read_text()))
        checks.append(
            Check(not bad, f"every number in the answer is in result.json (unexplained: {bad})")
        )
    return checks


def scenario_refused(cwd: Path) -> list[Check]:
    (cwd / "flat.csv").write_text(
        "date,sales\n" + "\n".join(f"2024-01-{d:02d},5" for d in range(1, 31)) + "\n"
    )
    t = run_claude("/forecast:forecast flat.csv", cwd)
    ANSWERS["refused"] = t.final_text
    text = t.final_text.lower()
    return [
        Check(
            "constant" in text
            or "same value" in text
            or "identical" in text
            or "every observation" in text,
            "explains that the series is constant",
        ),
        Check(
            not any("--" in c.split("flat.csv")[-1] for c in engine_calls(t)[1:]),
            "does not retry with other settings",
        ),
    ]


def scenario_horizon_too_long(cwd: Path) -> list[Check]:
    import datetime as dt

    start = dt.date(2024, 1, 1)
    rows = "\n".join(f"{start + dt.timedelta(days=i)},{100 + i}" for i in range(60))
    (cwd / "short.csv").write_text("date,sales\n" + rows + "\n")
    t = run_claude("/forecast:forecast short.csv --horizon 50", cwd)
    ANSWERS["horizon_too_long"] = t.final_text
    return [
        Check(
            bool(re.search(r"\b12\b", t.final_text)),
            "offers the maximum horizon the history supports (12)",
        ),
        Check(not (cwd / "forecast-output").exists(), "does not silently run a different horizon"),
    ]


SCENARIOS = {
    "forecast": scenario_forecast,
    "ambiguous": scenario_ambiguous,
    "natural_language": scenario_natural_language,
    "refused": scenario_refused,
    "horizon_too_long": scenario_horizon_too_long,
}


def main(names: list[str]) -> int:
    failed = 0
    for name in names or SCENARIOS:
        with tempfile.TemporaryDirectory() as tmp:
            print(f"\n== {name}")
            checks = SCENARIOS[name](Path(tmp))
            for check in checks:
                print(f"  [{'PASS' if check.ok else 'FAIL'}] {check.what}")
                failed += not check.ok
            if not all(c.ok for c in checks):
                print(
                    "  --- answer ---\n"
                    + "\n".join("  | " + ln for ln in ANSWERS.get(name, "").splitlines())
                )
    print(f"\n{'all checks passed' if not failed else f'{failed} check(s) failed'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
