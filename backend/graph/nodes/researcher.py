"""Researcher node.

Gathers raw inputs for a ticker:
  * MD&A text from the latest 10-K/10-Q (SEC EDGAR)
  * Fundamentals (yfinance)
  * Recent news (Tavily)

It also indexes the MD&A into Qdrant so the Analyst node can query specific
clauses. SEC + yfinance fetches run concurrently since they're independent I/O.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from backend.graph.state import ResearchState
from backend.rag.qdrant_store import index_mda
from backend.tools import get_financials, get_mda, get_recent_news

logger = logging.getLogger(__name__)


def researcher_node(state: ResearchState) -> dict[str, Any]:
    ticker = state["ticker"].strip().upper()
    logger.info("Researcher: gathering data for %s", ticker)
    errors: list[str] = []

    # MD&A (SEC) and fundamentals (yfinance) are independent — fetch in parallel.
    with ThreadPoolExecutor(max_workers=2) as pool:
        mda_future = pool.submit(get_mda, ticker)
        fin_future = pool.submit(get_financials, ticker)
        mda = mda_future.result()
        financials = fin_future.result()

    company_name = mda.get("company") or ticker
    if mda.get("error"):
        errors.append(f"SEC/MD&A: {mda['error']}")
    if financials.get("error"):
        errors.append(f"Financials: {financials['error']}")

    # News uses the resolved company name for better recall.
    news = get_recent_news(company_name)
    if news.get("error"):
        errors.append(f"News: {news['error']}")

    # Index MD&A for the Analyst's RAG queries.
    chunks_indexed = 0
    if mda.get("mda_text"):
        chunks_indexed = index_mda(
            ticker,
            mda["mda_text"],
            metadata={
                "form": mda.get("form"),
                "filing_date": mda.get("filing_date"),
                "source_url": mda.get("source_url"),
            },
        )
        if chunks_indexed == 0:
            errors.append("RAG: MD&A indexing returned 0 chunks (Qdrant unavailable?).")

    return {
        "company_name": company_name,
        "mda": mda,
        "financials": financials,
        "news": news,
        "chunks_indexed": chunks_indexed,
        "errors": errors,
    }
