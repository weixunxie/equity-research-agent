"""Plain-text renderings of the Researcher's data, shared by the Analyst and
Writer prompts so both nodes see the same figures."""
from __future__ import annotations

import statistics
from typing import Any

_PEER_METRICS = (
    "trailing_pe",
    "forward_pe",
    "ev_to_ebitda",
    "price_to_sales",
    "gross_margin",
    "operating_margin",
    "revenue_yoy",
)


def fmt_money(value: Any, currency: str | None = None) -> str:
    if value is None:
        return "n/a"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/a"
    sign = "-" if v < 0 else ""
    v = abs(v)
    cur = f"{currency} " if currency else ""
    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if v >= threshold:
            return f"{sign}{cur}{v / threshold:.2f}{suffix}"
    return f"{sign}{cur}{v:,.2f}"


def fmt_pct(value: Any) -> str:
    """Format a fraction (0.25) as a percentage (25.0%)."""
    return "n/a" if value is None else f"{float(value) * 100:.1f}%"


def fmt_mult(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.2f}x"


def _statement_table(rows: list[dict[str, Any]], cur: str | None) -> list[str]:
    lines = ["Period | Revenue | Gross profit | Operating income | Net income | Net margin"]
    for row in rows:
        rev, ni = row.get("revenue"), row.get("net_income")
        margin = fmt_pct(ni / rev) if rev and ni is not None else "n/a"
        lines.append(
            f"{row['period']} | {fmt_money(rev, cur)} | {fmt_money(row.get('gross_profit'), cur)}"
            f" | {fmt_money(row.get('operating_income'), cur)} | {fmt_money(ni, cur)} | {margin}"
        )
    return lines


def format_financials(fin: dict[str, Any]) -> str:
    cur = fin.get("currency")
    profile = fin.get("profile") or {}
    price = fin.get("price") or {}
    val = fin.get("valuation") or {}
    prof = fin.get("profitability") or {}
    growth = fin.get("growth") or {}
    bal = fin.get("balance") or {}
    analyst = fin.get("analyst") or {}

    lines = [
        f"Sector / industry: {profile.get('sector') or 'n/a'} / {profile.get('industry') or 'n/a'}",
        f"Price: {fmt_money(price.get('current'), cur)}"
        f" (52-week range {fmt_money(price.get('fifty_two_week_low'), cur)}"
        f" - {fmt_money(price.get('fifty_two_week_high'), cur)}; beta {price.get('beta') or 'n/a'})",
        f"Market cap: {fmt_money(val.get('market_cap'), cur)};"
        f" enterprise value: {fmt_money(val.get('enterprise_value'), cur)}",
        "Valuation: "
        f"trailing P/E {fmt_mult(val.get('trailing_pe'))}, forward P/E {fmt_mult(val.get('forward_pe'))},"
        f" PEG {fmt_mult(val.get('peg'))}, EV/EBITDA {fmt_mult(val.get('ev_to_ebitda'))},"
        f" P/S {fmt_mult(val.get('price_to_sales'))}, P/B {fmt_mult(val.get('price_to_book'))}",
        "Profitability (TTM): "
        f"gross margin {fmt_pct(prof.get('gross_margin'))}, operating margin"
        f" {fmt_pct(prof.get('operating_margin'))}, net margin {fmt_pct(prof.get('net_margin'))},"
        f" ROE {fmt_pct(prof.get('return_on_equity'))}",
        f"EPS: trailing {prof.get('trailing_eps') or 'n/a'}, forward {prof.get('forward_eps') or 'n/a'}",
        "Growth (latest quarter, year over year): "
        f"revenue {fmt_pct(growth.get('revenue_yoy'))}, earnings {fmt_pct(growth.get('earnings_yoy'))};"
        f" TTM revenue {fmt_money(growth.get('revenue_ttm'), cur)}",
        "Balance sheet / cash flow: "
        f"cash {fmt_money(bal.get('total_cash'), cur)}, debt {fmt_money(bal.get('total_debt'), cur)},"
        f" debt/equity {fmt_mult(bal.get('debt_to_equity'))}, current ratio"
        f" {fmt_mult(bal.get('current_ratio'))}, free cash flow (TTM)"
        f" {fmt_money(bal.get('free_cash_flow'), cur)}, operating cash flow (TTM)"
        f" {fmt_money(bal.get('operating_cash_flow'), cur)}",
    ]
    if analyst.get("target_mean") is not None:
        lines.append(
            "Sell-side consensus: "
            f"{analyst.get('recommendation') or 'n/a'} from"
            f" {int(analyst.get('analyst_count') or 0)} analysts; price target mean"
            f" {fmt_money(analyst.get('target_mean'), cur)} (low"
            f" {fmt_money(analyst.get('target_low'), cur)}, high"
            f" {fmt_money(analyst.get('target_high'), cur)}); implied move to mean"
            f" {fmt_pct(analyst.get('upside_to_mean'))}"
        )
    if fin.get("quarterly"):
        lines += ["", "Quarterly income statement (oldest first):"]
        lines += _statement_table(fin["quarterly"], cur)
    if fin.get("annual"):
        lines += ["", "Annual income statement (fiscal years, oldest first):"]
        lines += _statement_table(fin["annual"], cur)
    return "\n".join(lines)


def format_peers(peers: dict[str, Any], fin: dict[str, Any]) -> str:
    rows = list(peers.get("peers") or [])
    if not rows:
        return "No peer set available."
    val = fin.get("valuation") or {}
    prof = fin.get("profitability") or {}
    subject = {
        "ticker": f"{fin.get('ticker')} (subject)",
        "market_cap": val.get("market_cap"),
        "trailing_pe": val.get("trailing_pe"),
        "forward_pe": val.get("forward_pe"),
        "ev_to_ebitda": val.get("ev_to_ebitda"),
        "price_to_sales": val.get("price_to_sales"),
        "gross_margin": prof.get("gross_margin"),
        "operating_margin": prof.get("operating_margin"),
        "revenue_yoy": (fin.get("growth") or {}).get("revenue_yoy"),
    }
    lines = [
        f"Peer basis: {peers.get('basis') or 'n/a'}",
        "Ticker | Market cap | Trailing P/E | Forward P/E | EV/EBITDA | P/S | Gross margin"
        " | Operating margin | Revenue YoY",
    ]
    # Precomputed so the model compares against a figure rather than eyeballing one.
    median = {"ticker": "Peer median (excl. subject)", "market_cap": None}
    for key in _PEER_METRICS:
        values = [r[key] for r in rows if r.get(key) is not None]
        median[key] = statistics.median(values) if values else None
    for row in [subject, *rows, median]:
        lines.append(
            f"{row['ticker']} | {fmt_money(row.get('market_cap'))} | {fmt_mult(row.get('trailing_pe'))}"
            f" | {fmt_mult(row.get('forward_pe'))} | {fmt_mult(row.get('ev_to_ebitda'))}"
            f" | {fmt_mult(row.get('price_to_sales'))} | {fmt_pct(row.get('gross_margin'))}"
            f" | {fmt_pct(row.get('operating_margin'))} | {fmt_pct(row.get('revenue_yoy'))}"
        )
    return "\n".join(lines)


def format_news(news: dict[str, Any], snippet_chars: int = 500) -> str:
    parts: list[str] = []
    if news.get("answer"):
        parts.append(f"News summary: {news['answer']}")
    for item in (news.get("results") or [])[:8]:
        date = item.get("published_date") or "n/a"
        parts.append(f"- [{date}] {item.get('title')} ({item.get('url')})")
        snippet = " ".join((item.get("content") or "").split())[:snippet_chars]
        if snippet:
            parts.append(f"  {snippet}")
    return "\n".join(parts) if parts else "No recent news retrieved."
