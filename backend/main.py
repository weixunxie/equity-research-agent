"""FastAPI app exposing the equity research pipeline.

Run with:
    uvicorn backend.main:app --reload --port 8000

Endpoints:
    POST /research         -> blocking; returns the full ResearchResponse.
    POST /research/stream  -> Server-Sent Events; emits real per-node progress
                              ({researcher,analyst,writer} running/done), each
                              node's output as it lands (market data, then the
                              analysis, then the report token by token), and
                              finally the complete result.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
from collections.abc import Iterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.config import settings
from backend.graph.nodes.writer import build_sources
from backend.graph.pipeline import get_graph, run_research
from backend.guard import RateLimiter, TTLCache
from backend.models import Analysis, ResearchRequest, ResearchResponse
from backend.rag.qdrant_store import backend_kind

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Equity Research Agent",
    description="LangGraph pipeline (Researcher -> Analyst -> Writer) over SEC, yfinance, and news.",
    version="1.0.0",
)

# CORS for the Next.js frontend. Any origin by default so local dev and an
# existing deployment keep working; set ALLOWED_ORIGINS to the frontend's URL
# in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_origin_regex=settings.ALLOWED_ORIGIN_REGEX,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# CORS only restrains browsers, so the limits below are what actually caps
# spend: each uncached run costs LLM, embedding and search credits.
_ip_limiter = RateLimiter(settings.RATE_LIMIT_PER_HOUR, window=3600)
_global_limiter = RateLimiter(settings.RATE_LIMIT_PER_DAY, window=86400)
_cache: TTLCache[ResearchResponse] = TTLCache(settings.CACHE_TTL_MINUTES * 60)
_TICKER_RE = re.compile(r"[A-Z0-9][A-Z0-9.\-]{0,9}")

# Order of agent nodes, used to derive "next is running" transitions.
_STEPS = ("researcher", "analyst", "writer")
_NEWS_SNIPPET_CHARS = 320


def _news_items(news: dict) -> list[dict]:
    """Trim raw Tavily results to what the UI renders."""
    items = []
    for item in news.get("results") or []:
        if not (item.get("title") and item.get("url")):
            continue
        snippet = " ".join((item.get("content") or "").split())
        items.append(
            {
                "title": item["title"],
                "url": item["url"],
                "source": item.get("source"),
                "published_date": item.get("published_date"),
                "snippet": snippet[:_NEWS_SNIPPET_CHARS] or None,
            }
        )
    return items


def _data_payload(ticker: str, state: dict) -> dict:
    """Everything the Researcher gathered that the UI shows directly: market
    data, peers, news, sources and run metadata. Emitted as soon as the
    Researcher finishes, and included again in the final response."""
    mda = state.get("mda", {}) or {}
    news = state.get("news", {}) or {}
    metadata = {
        "chunks_indexed": state.get("chunks_indexed", 0),
        "rag_backend": backend_kind() if state.get("chunks_indexed") else None,
        "sec_form": mda.get("form"),
        "filing_date": mda.get("filing_date"),
        "source_url": mda.get("source_url"),
        "annual_form": mda.get("annual_form"),
        "annual_filing_date": mda.get("annual_filing_date"),
        "sections": {
            "mda": len(mda.get("mda_text") or ""),
            "risk_factors": len(mda.get("risk_factors_text") or ""),
            "business": len(mda.get("business_text") or ""),
        },
        "news_count": len(news.get("results") or []),
        "peer_basis": (state.get("peers") or {}).get("basis"),
        "chat_model": settings.CHAT_MODEL,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "cached": False,
    }
    return {
        "ticker": ticker,
        "company": state.get("company_name", ticker),
        "financials": state.get("financials") or {},
        "peers": (state.get("peers") or {}).get("peers") or [],
        "news": _news_items(news),
        "sources": build_sources(state),
        "metadata": metadata,
    }


def _build_response(ticker: str, state: dict) -> ResearchResponse:
    """Assemble the API response from a final graph state. Shared by both the
    blocking and streaming endpoints."""
    analysis_dict = state.get("analysis")
    analysis = None
    if analysis_dict:
        try:
            analysis = Analysis(**analysis_dict)
        except Exception:  # noqa: BLE001 - return report even if schema drifts
            logger.warning("Analysis failed schema validation; returning report only.")

    return ResearchResponse(
        **_data_payload(ticker, state),
        report_markdown=state.get("report_markdown", ""),
        analysis=analysis,
        errors=state.get("errors", []),
    )


def _sse(payload: dict) -> str:
    """Format a dict as a Server-Sent Events `data:` frame."""
    return f"data: {json.dumps(payload)}\n\n"


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "equity-research-agent", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "config_warnings": settings.validate()}


def _parse_ticker(raw: str) -> str:
    ticker = raw.strip().upper()
    if not _TICKER_RE.fullmatch(ticker):
        raise HTTPException(
            status_code=400,
            detail="`ticker` must be 1-10 characters: letters, digits, '.' or '-'.",
        )
    return ticker


def _client_ip(request: Request) -> str:
    """The caller's address. Behind a reverse proxy (Railway) the socket peer is
    the proxy, and the proxy appends the real client to X-Forwarded-For — so the
    last entry is the one a client can't forge."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _cached(ticker: str, refresh: bool) -> ResearchResponse | None:
    hit = None if refresh else _cache.get(ticker)
    if hit is None:
        return None
    return hit.model_copy(update={"metadata": {**hit.metadata, "cached": True}})


def _admit(request: Request) -> None:
    """Count one pipeline run against the caller's and the global budget, or
    reject it with 429 and a Retry-After."""
    ip = _client_ip(request)
    waits = (
        (_ip_limiter.retry_after(ip), "You've reached the hourly limit for new reports."),
        (_global_limiter.retry_after("all"), "The service has reached today's report limit."),
    )
    for wait, reason in waits:
        if wait > 0:
            minutes = max(1, round(wait / 60))
            raise HTTPException(
                status_code=429,
                detail=f"{reason} Try again in about {minutes} min.",
                headers={"Retry-After": str(int(wait) + 1)},
            )
    _ip_limiter.hit(ip)
    _global_limiter.hit("all")


def _remember(ticker: str, result: ResearchResponse) -> None:
    """Cache a run unless an LLM step fell back — a degraded report shouldn't
    be served to the next caller for an hour."""
    degraded = any(e.startswith(("Analyst:", "Writer:")) for e in result.errors)
    if result.report_markdown and result.analysis and not degraded:
        _cache.set(ticker, result)


@app.post("/research", response_model=ResearchResponse)
def research(request: ResearchRequest, http_request: Request) -> ResearchResponse:
    ticker = _parse_ticker(request.ticker)
    cached = _cached(ticker, request.refresh)
    if cached:
        return cached
    _admit(http_request)

    try:
        state = run_research(ticker)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed for %s", ticker)
        raise HTTPException(status_code=500, detail=f"Research pipeline failed: {exc}")

    result = _build_response(ticker, state)
    _remember(ticker, result)
    return result


@app.post("/research/stream")
def research_stream(request: ResearchRequest, http_request: Request) -> StreamingResponse:
    """Stream the run as it happens.

    LangGraph's ``updates`` mode yields ``{node_name: update}`` after each node
    completes, and ``messages`` mode yields LLM tokens as they're generated. The
    stream carries, in order:

    * ``step``     — a node started / finished (real progress, not a timer)
    * ``data``     — market data, peers, news and sources (after the Researcher)
    * ``analysis`` — the structured analysis (after the Analyst)
    * ``token``    — report markdown chunks (while the Writer runs)
    * ``result``   — the complete ``ResearchResponse``

    A cached report is sent as a single ``result`` event.
    """
    ticker = _parse_ticker(request.ticker)
    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    cached = _cached(ticker, request.refresh)
    if cached:
        return StreamingResponse(
            iter([_sse({"type": "result", "data": cached.model_dump()})]),
            media_type="text/event-stream",
            headers=headers,
        )
    _admit(http_request)

    def event_gen() -> Iterator[str]:
        # The first node begins as soon as we start consuming the stream.
        yield _sse({"type": "step", "step": "researcher", "status": "running"})
        state: dict = {"ticker": ticker, "errors": []}
        try:
            for mode, chunk in get_graph().stream(
                {"ticker": ticker, "errors": []}, stream_mode=["updates", "messages"]
            ):
                if mode == "messages":
                    message, meta = chunk
                    text = getattr(message, "content", "")
                    if meta.get("langgraph_node") == "writer" and isinstance(text, str) and text:
                        yield _sse({"type": "token", "text": text})
                    continue

                for node_name, update in chunk.items():
                    # Merge this node's update into the running state. `errors`
                    # is additive (matches the graph's reducer); others overwrite.
                    for key, value in (update or {}).items():
                        if key == "errors" and isinstance(value, list):
                            state.setdefault("errors", []).extend(value)
                        else:
                            state[key] = value

                    if node_name not in _STEPS:
                        continue
                    if node_name == "researcher":
                        yield _sse(
                            {
                                "type": "data",
                                "data": _data_payload(ticker, state),
                                "errors": state.get("errors", []),
                            }
                        )
                    elif node_name == "analyst":
                        yield _sse({"type": "analysis", "data": state.get("analysis")})
                    yield _sse({"type": "step", "step": node_name, "status": "done"})
                    i = _STEPS.index(node_name)
                    if i + 1 < len(_STEPS):
                        yield _sse({"type": "step", "step": _STEPS[i + 1], "status": "running"})

            result = _build_response(ticker, state)
            _remember(ticker, result)
            yield _sse({"type": "result", "data": result.model_dump()})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Streaming pipeline failed for %s", ticker)
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers=headers,
    )
