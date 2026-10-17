"""Run the research pipeline from the terminal (no API/UI needed).

Usage:
    python -m scripts.research_cli AAPL
"""
from __future__ import annotations

import sys

from backend.graph import run_research
from backend.tools.ticker_check import (
    TickerCheckUnavailable,
    UnknownTickerError,
    validate_ticker,
)


def main() -> int:
    ticker = (sys.argv[1] if len(sys.argv) > 1 else "AAPL").strip().upper()
    try:
        validate_ticker(ticker)
    except (UnknownTickerError, TickerCheckUnavailable) as exc:
        print(exc, file=sys.stderr)
        return 1
    state = run_research(ticker)

    print(state.get("report_markdown", "(no report generated)"))

    errors = state.get("errors") or []
    if errors:
        print("\n\n--- pipeline warnings ---", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
