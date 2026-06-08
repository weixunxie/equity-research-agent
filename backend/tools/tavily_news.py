"""Recent-news retrieval via the Tavily search API."""
from __future__ import annotations

import logging
from typing import Any

from backend.config import settings

logger = logging.getLogger(__name__)


def get_recent_news(
    company_name: str, days: int | None = None, max_results: int = 8
) -> dict[str, Any]:
    """Fetch recent news for a company over the last ``days`` days.

    Returns a stable shape with a list of articles and an optional Tavily-
    generated summary ``answer``. Degrades gracefully (empty results + error)
    when the API key is missing or the call fails.
    """
    days = days or settings.NEWS_LOOKBACK_DAYS
    out: dict[str, Any] = {
        "query": company_name,
        "lookback_days": days,
        "answer": None,
        "results": [],
        "error": None,
    }

    if not settings.TAVILY_API_KEY:
        out["error"] = "TAVILY_API_KEY not set; skipping news retrieval."
        return out

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        resp = client.search(
            query=f"{company_name} stock news and developments",
            topic="news",
            days=days,
            max_results=max_results,
            include_answer=True,
            search_depth="advanced",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tavily news search failed for %s: %s", company_name, exc)
        out["error"] = f"Tavily search failed: {exc}"
        return out

    out["answer"] = resp.get("answer")
    for item in resp.get("results", []):
        out["results"].append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "content": item.get("content"),
                "published_date": item.get("published_date"),
                "score": item.get("score"),
            }
        )
    return out
