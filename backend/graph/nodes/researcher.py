"""Researcher node.

Gathers raw inputs for a ticker:
  * MD&A, Risk Factors and Business sections from the latest filings (SEC EDGAR)
  * Market data and fundamentals, plus a peer set (yfinance)
  * Recent news (Tavily)

It also indexes the filing sections into Qdrant so the Analyst node can query
specific clauses. The SEC and yfinance fetches run concurrently since they're
independent I/O.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from backend.graph.state import ResearchState
from backend.rag.qdrant_store import index_sections
from backend.tools import get_filing_sections, get_financials, get_peers, get_recent_news

logger = logging.getLogger(__name__)


def researcher_node(state: ResearchState) -> dict[str, Any]:
    ticker = state["ticker"].strip().upper()
    logger.info("Researcher: gathering data for %s", ticker)
    errors: list[str] = []

    # Filings (SEC), fundamentals and peers (yfinance) are independent — fetch in parallel.
    with ThreadPoolExecutor(max_workers=3) as pool:
        mda_future = pool.submit(get_filing_sections, ticker)
        fin_future = pool.submit(get_financials, ticker)
        peers_future = pool.submit(get_peers, ticker)
        mda = mda_future.result()
        financials = fin_future.result()
        peers = peers_future.result()

    profile_name = (financials.get("profile") or {}).get("name")
    company_name = profile_name or mda.get("company") or ticker
    if mda.get("error"):
        errors.append(f"SEC filings: {mda['error']}")
    elif not mda.get("risk_factors_text"):
        errors.append("SEC filings: Risk Factors section could not be extracted.")
    if financials.get("error"):
        errors.append(f"Financials: {financials['error']}")
    if peers.get("error"):
        errors.append(f"Peers: {peers['error']}")

    # News uses the resolved company name for better recall.
    news = get_recent_news(company_name)
    if news.get("error"):
        errors.append(f"News: {news['error']}")

    # Index filing sections for the Analyst's RAG queries.
    periodic = {
        "form": mda.get("form"),
        "filing_date": mda.get("filing_date"),
        "source_url": mda.get("source_url"),
    }
    annual = {
        "form": mda.get("annual_form"),
        "filing_date": mda.get("annual_filing_date"),
        "source_url": mda.get("annual_source_url"),
    }
    sections = {
        "mda": mda.get("mda_text") or "",
        "risk_factors": mda.get("risk_factors_text") or "",
        "business": mda.get("business_text") or "",
    }
    chunks_indexed = 0
    if any(sections.values()):
        chunks_indexed = index_sections(
            ticker,
            sections,
            metadata={"mda": periodic, "risk_factors": annual, "business": annual},
        )
        if chunks_indexed == 0:
            errors.append("RAG: filing indexing returned 0 chunks (Qdrant unavailable?).")

    return {
        "company_name": company_name,
        "mda": mda,
        "financials": financials,
        "peers": peers,
        "news": news,
        "chunks_indexed": chunks_indexed,
        "errors": errors,
    }
