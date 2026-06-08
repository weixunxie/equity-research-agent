"""Shared state object threaded through the LangGraph pipeline."""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class ResearchState(TypedDict, total=False):
    """State accumulated as the graph runs.

    ``total=False`` lets each node return only the keys it produces; LangGraph
    merges them into the running state. ``errors`` uses an additive reducer so
    non-fatal problems from every node are collected rather than overwritten.
    """

    # Input
    ticker: str

    # Researcher outputs
    company_name: str
    mda: dict[str, Any]
    financials: dict[str, Any]
    news: dict[str, Any]
    chunks_indexed: int

    # Analyst output (serialized Analysis model)
    analysis: dict[str, Any]

    # Writer output
    report_markdown: str

    # Diagnostics (accumulated across nodes)
    errors: Annotated[list[str], operator.add]
