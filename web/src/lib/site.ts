// Single place for site-wide constants.
// TODO: confirm the repository URL before launch. This is taken from the
// `repository` field in ../.claude-plugin/plugin.json.
export const REPO_URL = "https://github.com/mkaavish/forecastClaudeSkill";

export const SITE_URL = "https://forecast-skill.vercel.app";

export const TITLE = "/forecast — Time-series forecasting for Claude Code";
export const DESCRIPTION =
  "An open-source Claude Code skill for statistically backtested time-series forecasting, automatic model selection, and plain-English analysis.";

export const DOCS_NAV = [
  { href: "/docs", label: "Getting started" },
  { href: "/docs/usage", label: "Usage" },
  { href: "/docs/how-it-works", label: "How it works" },
  { href: "/docs/models", label: "Models & backtesting" },
  { href: "/docs/outputs", label: "Outputs" },
  { href: "/docs/statistical-integrity", label: "Statistical integrity" },
] as const;
