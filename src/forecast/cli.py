"""Command-line entry point (Phase 0 stub: only --version)."""

from __future__ import annotations

import argparse

from forecast import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forecast")
    parser.add_argument("--version", action="version", version=f"forecast {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0
