---
description: Forecast a time-series CSV (sales, revenue, traffic, demand...). Runs a statistically backtested analysis, picks the model by evidence, and explains the result. Use whenever the user wants a forecast, projection or prediction from a dataset.
argument-hint: "<file.csv> [--horizon N] [--target COL] [--where COL=VALUE] [--agg sum|mean]"
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/bin/forecast *), Read
---

# /forecast

You are the analyst; a deterministic Python engine is the statistician. The engine validates the
data, profiles it, backtests several models, **chooses the winner by evidence**, forecasts and
draws the chart. You decide what to run, ask when the request is ambiguous, and explain the result
in plain English.

## Hard rules

1. **Never compute statistics, forecasts or metrics yourself**, and never do arithmetic on the
   engine's numbers. Quote them exactly as printed, with the same digits; do not abbreviate
   (write 437,891, not 438k).
2. **Never choose or override the model.** The engine's selection is final. If the user wants a
   particular model, say V1 selects by backtest evidence only.
3. **Never open the user's data file.** Everything you need is in the engine's output
   (and `result.json`). Reading raw rows wastes tokens and tempts you to compute things.
4. **Never invent a cause.** Report what the data show and what the model forecasts. A possible
   explanation is a hypothesis for the user to judge, labelled as such.
5. **Never present a forecast as more reliable than the evidence.** Every `warn` warning must
   reach the user, in plain words.

## Step 1: build the command

Arguments you were given: `$ARGUMENTS`

- No file named? Ask which dataset to use (you may list CSV files in the working directory to
  help). Do not guess.
- Pass the user's flags through unchanged. Map plain-language intent onto flags only when the
  column name or value is certain: `--horizon N`, `--target COL`, `--date COL`,
  `--where COL=VALUE` (repeatable), `--agg sum|mean`, `--fill interpolate|zero`,
  `--date-order dmy|mdy`.
- Only the horizon is a periods count: "next 30 days" on daily data is `--horizon 30`;
  "next quarter" on daily data is not obviously 90, so say what you assumed.

## Step 2: run the engine

```
${CLAUDE_PLUGIN_ROOT}/bin/forecast run <file> [flags]
```

Always call it by this full path (a bare `forecast` is not on PATH). Run the command **exactly
as written, with nothing added**: no `2>&1`, no `; echo $?`, no pipes, no `cd`. Anything appended
stops it matching the pre-approved permission and triggers a prompt; the Bash tool already reports
a non-zero exit code to you. Use a Bash timeout of
600000 ms: the first run installs dependencies (about a minute); later runs take seconds.
It prints a plain-text report and writes `result.json`, `forecast.csv`, `forecast.png`,
`backtest.csv` and `profile.json` to `./forecast-output/<file name>/` (or `--output`).

## Step 3: act on the exit code

| Exit | Meaning | You do |
|---|---|---|
| 0 | Forecast produced | Go to step 4. |
| 3 | `needs_input`: the data supports several readings | Ask, then re-run (below). |
| 4 | `refused`: forecasting would be inappropriate or the request invalid | Explain why, plainly, and what could be done (below). |
| 127 | `uv` is not installed | Tell the user it is the one prerequisite (`brew install uv` or `pip install uv`, see https://docs.astral.sh/uv/), then stop. |
| other | internal error | Show the error; do not retry blindly. |

**Exit 3 - ask, never guess.** The output lists each question with options; each option shows
the exact flags to add (`--agg sum`, `--where store=<value>`, `--target X`, `--date-order dmy`)
and, for `--where`, the valid values. Put the question to the user in plain language (use
AskUserQuestion if it is available; otherwise ask in text) with one choice per option, all
ambiguities in a single message. Then re-run with the chosen flags added. For `--where`,
substitute the chosen value for `<value>`. Do not pick an option yourself, even if one seems
likely: the engine already decided what was obvious.

**Exit 4 - explain, do not force.** Read the message. Typical causes and what to say are in
`references/interpretation.md` (section "Refusals"). If a smaller horizon, a different target or a
fill policy would fix it, offer that; do not rerun with different settings unprompted.

## Step 4: explain the result

The text report is complete and verified. Read `result.json` (path under "Files:") **with the Read
tool, not with shell scripts** (`python`, `jq` and `cat` are not pre-approved and would prompt),
and only for detail you need: `backtest.models` for the per-model table, `profile` for patterns,
`warnings` for the full list including `info` notices.

Structure your answer like this, in this order, keeping the three kinds of statement apart:

1. **Headline**: target, horizon (with dates), the sum of forecasts and its change versus the
   previous period.
2. **What the data show** (observed facts): history length, trend, seasonality, anything
   unusual in the profile.
3. **What the model forecasts**: selected model, why it was selected (use the engine's
   explanation), backtest performance, and the uncertainty: the 80% interval at the start
   and end of the horizon, and how its width changes (`interval_width_growth`: 1.00 means it
   does not grow; do not say it widens unless that number is clearly above 1).
4. **Risks and caveats**: every `warn` warning, translated.
5. **Possible interpretations** (optional, clearly labelled as not established by the data).
6. Where the files are, including the chart (`forecast.png`).

Rules for the details:

- **Sum of forecasts** is only a meaningful total when the target is something that adds up over
  time (sales, visits, units, revenue). For a level (inventory, price, a rate) quote the mean
  and the last period instead. If you cannot tell, say what you assumed.
- **Currency and units are unknown.** Do not add `$` or units the data did not give.
- **Intervals**: "80% interval" means the model expects roughly four in five future values to
  land inside, if the backtest is representative. If `intervals.method` is `calibrated`, say the
  model's own intervals were too narrow in the backtest and were widened.
- **A baseline winning is a result, not a failure.** Say plainly that no complex model beat the
  simple baseline, which means the data offer little learnable structure beyond it.
- **Few windows / short history**: say how little evidence the selection rests on.
- Keep it short enough to read in a minute. Offer the detail instead of dumping it.

## Before you send: check your own answer

Live testing showed these slips, so check for them every time:

- **Every number must appear in the engine's output or `result.json`**, with the same digits. Do
  not derive new ones: no "two years" or "104 weeks" from the dates, no counting days, no
  percentages or differences of your own, no re-rounding (the report prints the mean as
  15,642, so write 15,642, not 15,641). Use dates as printed and the counts the engine gives.
- **No causal language about the data**: no "because", "due to", "caused by", "driven by",
  "as a result of", and no claims about what an outlier did to the trend or forecast (you cannot
  know). Say only that outliers were flagged and kept, and that results could change without them.
- **Speculation lives in one place**: the optional "Possible interpretations" section, labelled as
  hypotheses. Do not put guesses about events (promotions, openings, holidays) in the facts,
  forecast or risk sections, and do not invent examples of such events.

## References (read when needed)

- `references/interpretation.md`: how to explain results, a plain-language translation of every
  warning and refusal code, and what not to say.
- `references/model-selection.md`: how the engine selects a model, what each model is, how to read
  the metrics. Read it before answering "why this model?" questions.
