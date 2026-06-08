"""Run the research pipeline from the terminal (no API/UI needed).

Usage:
    python -m scripts.research_cli AAPL
"""
from __future__ import annotations

import sys

from backend.graph import run_research


def main() -> int:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
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
