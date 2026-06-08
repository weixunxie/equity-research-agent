"""LangGraph assembly: Researcher -> Analyst -> Writer."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from langgraph.graph import END, START, StateGraph

from backend.graph.nodes import analyst_node, researcher_node, writer_node
from backend.graph.state import ResearchState

logger = logging.getLogger(__name__)


def build_graph():
    """Construct and compile the linear 3-node pipeline."""
    graph = StateGraph(ResearchState)
    graph.add_node("researcher", researcher_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("writer", writer_node)

    graph.add_edge(START, "researcher")
    graph.add_edge("researcher", "analyst")
    graph.add_edge("analyst", "writer")
    graph.add_edge("writer", END)

    return graph.compile()


@lru_cache
def get_graph():
    """Compile the graph once and reuse it across requests."""
    return build_graph()


def run_research(ticker: str) -> dict[str, Any]:
    """Run the full pipeline for a ticker and return the final state."""
    ticker = ticker.strip().upper()
    logger.info("Running research pipeline for %s", ticker)
    initial: ResearchState = {"ticker": ticker, "errors": []}
    return get_graph().invoke(initial)
