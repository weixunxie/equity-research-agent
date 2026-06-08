"""Analyst node.

Synthesizes the Researcher's raw data into a structured ``Analysis`` (bull case,
bear case, key risks, sentiment, financial summary). It augments the prompt with
specific MD&A clauses retrieved from Qdrant (RAG), and falls back to a
data-derived stub if the LLM is unavailable so the pipeline always completes.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.graph.state import ResearchState
from backend.llm import get_chat_model
from backend.models import Analysis, FinancialSummary, Sentiment
from backend.rag.qdrant_store import query_filings

logger = logging.getLogger(__name__)

# Targeted clauses to pull from the MD&A for grounding.
_RAG_QUERIES = [
    "risk factors and material uncertainties",
    "liquidity and capital resources",
    "revenue growth drivers and demand trends",
    "competition and pricing pressure",
]

_SYSTEM_PROMPT = (
    "You are a rigorous, balanced equity research analyst. Using ONLY the data "
    "provided (fundamentals, recent news, and excerpts from the company's latest "
    "SEC MD&A), produce a structured analysis. Be specific and cite concrete "
    "figures where available. Give a genuinely balanced bull and bear case; do "
    "not be promotional. If data is missing, say so rather than inventing it."
)


def _fmt_money(value: Any, currency: str | None = None) -> str:
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
    return f"{sign}{cur}{v:,.0f}"


def _format_financials(fin: dict[str, Any]) -> str:
    cur = fin.get("currency")
    lines = [
        f"- P/E (trailing): {fin.get('pe_ratio') if fin.get('pe_ratio') is not None else 'n/a'}",
        f"- Debt/Equity: {fin.get('debt_to_equity') if fin.get('debt_to_equity') is not None else 'n/a'}",
        f"- Free cash flow: {_fmt_money(fin.get('free_cash_flow'), cur)}",
        f"- Market cap: {_fmt_money(fin.get('market_cap'), cur)}",
    ]
    rev = fin.get("revenue_quarterly") or []
    if rev:
        rev_str = ", ".join(
            f"{p['period']}: {_fmt_money(p['value'], cur)}" for p in rev
        )
        lines.append(f"- Revenue (last 4 quarters): {rev_str}")
    ni = fin.get("net_income_quarterly") or []
    if ni:
        ni_str = ", ".join(f"{p['period']}: {_fmt_money(p['value'], cur)}" for p in ni)
        lines.append(f"- Net income (last 4 quarters): {ni_str}")
    return "\n".join(lines)


def _format_news(news: dict[str, Any]) -> str:
    parts: list[str] = []
    if news.get("answer"):
        parts.append(f"News summary: {news['answer']}")
    for item in (news.get("results") or [])[:8]:
        date = item.get("published_date") or "n/a"
        parts.append(f"- [{date}] {item.get('title')} ({item.get('url')})")
    return "\n".join(parts) if parts else "No recent news retrieved."


def _gather_rag_context(ticker: str) -> str:
    """Pull targeted MD&A excerpts from Qdrant for grounding."""
    seen: set[int] = set()
    blocks: list[str] = []
    for query in _RAG_QUERIES:
        for hit in query_filings(ticker, query, top_k=2):
            idx = hit.get("chunk_index")
            if idx in seen:
                continue
            seen.add(idx)
            text = (hit.get("text") or "").strip()
            if text:
                blocks.append(f"[{query}] {text[:1200]}")
    return "\n\n".join(blocks)


def _fallback_analysis(state: ResearchState, reason: str) -> dict[str, Any]:
    """Deterministic, data-derived analysis used when the LLM is unavailable."""
    fin = state.get("financials", {})
    news = state.get("news", {})
    headlines = [i.get("title") for i in (news.get("results") or [])[:5] if i.get("title")]
    analysis = Analysis(
        bull_case=["LLM analysis unavailable — see raw financials and news below."],
        bear_case=["LLM analysis unavailable — see raw financials and news below."],
        key_risks=["Automated analysis could not be generated: " + reason],
        recent_sentiment=Sentiment(
            label="neutral",
            summary=news.get("answer") or "No sentiment synthesis available.",
            notable_headlines=headlines,
        ),
        financial_summary=FinancialSummary(
            pe_ratio=fin.get("pe_ratio"),
            debt_to_equity=fin.get("debt_to_equity"),
            free_cash_flow=fin.get("free_cash_flow"),
            revenue_trend="See raw quarterly revenue figures.",
            net_income_trend="See raw quarterly net income figures.",
            commentary="Generated without LLM synthesis.",
        ),
    )
    return analysis.model_dump()


def analyst_node(state: ResearchState) -> dict[str, Any]:
    ticker = state["ticker"].strip().upper()
    company = state.get("company_name", ticker)
    logger.info("Analyst: synthesizing analysis for %s", ticker)

    fin = state.get("financials", {})
    news = state.get("news", {})
    mda = state.get("mda", {})

    rag_context = _gather_rag_context(ticker)
    if not rag_context:
        # Qdrant empty/unavailable — fall back to a slice of raw MD&A text.
        rag_context = (mda.get("mda_text") or "")[:4000] or "No MD&A text available."

    user_content = f"""Company: {company} ({ticker})
SEC filing: {mda.get('form') or 'n/a'} dated {mda.get('filing_date') or 'n/a'}

=== FUNDAMENTALS ===
{_format_financials(fin)}

=== RECENT NEWS (last {news.get('lookback_days', 30)} days) ===
{_format_news(news)}

=== MD&A EXCERPTS (retrieved) ===
{rag_context}
"""

    try:
        model = get_chat_model(temperature=0.2).with_structured_output(Analysis)
        analysis: Analysis = model.invoke(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ]
        )
        return {"analysis": analysis.model_dump()}
    except Exception as exc:  # noqa: BLE001 - keep the pipeline alive
        logger.warning("Analyst LLM call failed for %s: %s", ticker, exc)
        return {
            "analysis": _fallback_analysis(state, str(exc)),
            "errors": [f"Analyst: LLM synthesis failed ({exc})."],
        }
