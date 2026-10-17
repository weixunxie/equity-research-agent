"""Analyst node.

Synthesizes the Researcher's raw data into a structured ``Analysis`` (thesis,
stance, bull/bear case, catalysts, risks, valuation view, sentiment, financial
summary). A run with neither filing text nor fundamentals gets no analysis at
all — there is nothing to ground a view in. Otherwise it grounds the prompt in filing excerpts retrieved from Qdrant —
queried per section, so risks come from Item 1A, operating trends from the MD&A
and the business model from Item 1 — and falls back to a data-derived stub if
the LLM is unavailable so the pipeline always completes.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.errors import describe_error
from backend.graph.formatting import format_financials, format_news, format_peers
from backend.graph.state import ResearchState
from backend.llm import get_chat_model
from backend.models import Analysis, FinancialSummary, Sentiment
from backend.rag.qdrant_store import query_filings

logger = logging.getLogger(__name__)

# Targeted clauses to pull from each filing section for grounding.
_RAG_QUERIES: dict[str, list[str]] = {
    "risk_factors": [
        "most significant risks to revenue and profitability",
        "regulatory, legal, trade and geopolitical risks",
        "competition, customer concentration and supply chain dependence",
    ],
    "mda": [
        "revenue growth drivers, segment performance and demand trends",
        "gross margin, operating expenses and profitability changes",
        "liquidity, capital resources, debt and capital returns",
    ],
    "business": [
        "products, services, segments and how the company makes money",
        "competitive position, customers and markets",
    ],
}
_SECTION_TITLES = {
    "risk_factors": "RISK FACTORS (latest annual report)",
    "mda": "MD&A (latest periodic report)",
    "business": "BUSINESS (latest annual report)",
}
_SECTION_TEXT_KEYS = {
    "risk_factors": "risk_factors_text",
    "mda": "mda_text",
    "business": "business_text",
}
INSUFFICIENT_DATA = "Not enough source data to form a view"
_EXCERPT_CHARS = 1500
_RAW_FALLBACK_CHARS = 5000

_SYSTEM_PROMPT = (
    "You are a rigorous, balanced equity research analyst. Using ONLY the data "
    "provided (market data and fundamentals, a peer comparison, recent news, and "
    "excerpts from the company's SEC filings), produce a structured analysis.\n"
    "- Be specific: cite concrete figures (growth rates, margins, multiples, "
    "dollar amounts) in the bull/bear points, the valuation view and the "
    "financial summary.\n"
    "- Give 4-6 bull points, 4-6 bear points, 3-5 catalysts and 5-7 key risks. "
    "Draw risks from the Risk Factors excerpts and name the specific exposure, "
    "not generic boilerplate.\n"
    "- The valuation view must compare the company's multiples with the peer "
    "table and relate them to its growth and margins. Before calling a multiple "
    "high or low, check it against the peer median row and each peer's figure; "
    "a multiple below the peer median is a discount, not a premium.\n"
    "- The stance is an analytical lean implied by the evidence, not a "
    "recommendation; do not be promotional.\n"
    "- If data is missing, say so rather than inventing it."
)


def has_source_data(state: ResearchState) -> bool:
    """Whether the Researcher found any filing text or fundamentals. News and a
    price chart alone are not enough to write a thesis from."""
    mda = state.get("mda") or {}
    if any(mda.get(key) for key in _SECTION_TEXT_KEYS.values()):
        return True
    fin = state.get("financials") or {}
    return bool(
        fin.get("quarterly")
        or fin.get("annual")
        or any(v is not None for v in (fin.get("valuation") or {}).values())
        or (fin.get("growth") or {}).get("revenue_ttm") is not None
    )


def _gather_rag_context(ticker: str, mda: dict[str, Any]) -> str:
    """Pull targeted excerpts per filing section from Qdrant; for a section with
    no hits (nothing indexed, store unavailable) use the head of its raw text."""
    parts: list[str] = []
    for section, queries in _RAG_QUERIES.items():
        seen: set[int] = set()
        blocks: list[str] = []
        for query in queries:
            for hit in query_filings(ticker, query, top_k=2, section=section):
                idx = hit.get("chunk_index")
                text = (hit.get("text") or "").strip()
                if idx in seen or not text:
                    continue
                seen.add(idx)
                blocks.append(f"[{query}] {text[:_EXCERPT_CHARS]}")
        if not blocks:
            raw = (mda.get(_SECTION_TEXT_KEYS[section]) or "")[:_RAW_FALLBACK_CHARS]
            if raw:
                blocks.append(raw)
        if blocks:
            parts.append(f"--- {_SECTION_TITLES[section]} ---\n" + "\n\n".join(blocks))
    return "\n\n".join(parts) or "No filing text available."


def _fallback_analysis(state: ResearchState, reason: str) -> dict[str, Any]:
    """Deterministic, data-derived analysis used when the LLM is unavailable."""
    fin = state.get("financials", {})
    news = state.get("news", {})
    summary = (fin.get("profile") or {}).get("summary")
    headlines = [i.get("title") for i in (news.get("results") or [])[:5] if i.get("title")]
    unavailable = "LLM analysis unavailable — see the raw financials and news."
    analysis = Analysis(
        thesis="Automated analysis could not be generated: " + reason,
        stance="neutral",
        stance_rationale="No synthesis was produced, so no lean is implied.",
        business_overview=summary or "No business description available.",
        bull_case=[unavailable],
        bear_case=[unavailable],
        catalysts=[],
        key_risks=[],
        valuation_view="See the valuation multiples and peer table.",
        recent_sentiment=Sentiment(
            label="neutral",
            summary=news.get("answer") or "No sentiment synthesis available.",
            notable_headlines=headlines,
        ),
        financial_summary=FinancialSummary(
            revenue_trend="See the quarterly and annual revenue figures.",
            profitability_trend="See the margin and net income figures.",
            balance_sheet="See the cash, debt and cash-flow figures.",
            commentary="Generated without LLM synthesis.",
        ),
    )
    return analysis.model_dump()


def analyst_node(state: ResearchState) -> dict[str, Any]:
    ticker = state["ticker"].strip().upper()
    company = state.get("company_name", ticker)
    if not has_source_data(state):
        logger.info("Analyst: no filings or financials for %s; skipping analysis", ticker)
        return {"errors": [f"Analyst: {INSUFFICIENT_DATA} (no SEC filings or financials found)."]}
    logger.info("Analyst: synthesizing analysis for %s", ticker)

    fin = state.get("financials", {})
    news = state.get("news", {})
    mda = state.get("mda", {})
    peers = state.get("peers", {})

    user_content = f"""Company: {company} ({ticker})
Latest periodic filing: {mda.get('form') or 'n/a'} dated {mda.get('filing_date') or 'n/a'}
Latest annual filing: {mda.get('annual_form') or 'n/a'} dated {mda.get('annual_filing_date') or 'n/a'}

=== MARKET DATA & FUNDAMENTALS ===
{format_financials(fin)}

=== PEER COMPARISON ===
{format_peers(peers, fin)}

=== RECENT NEWS (last {news.get('lookback_days', 30)} days) ===
{format_news(news)}

=== SEC FILING EXCERPTS (retrieved) ===
{_gather_rag_context(ticker, mda)}
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
        reason = describe_error(exc)
        return {
            "analysis": _fallback_analysis(state, reason),
            "errors": [f"Analyst: LLM synthesis failed ({reason})."],
        }
