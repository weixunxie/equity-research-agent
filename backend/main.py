"""FastAPI app exposing the equity research pipeline.

Run with:
    uvicorn backend.main:app --reload --port 8000

Endpoints:
    POST /research         -> blocking; returns the full ResearchResponse.
    POST /research/stream  -> Server-Sent Events; emits real per-node progress
                              ({researcher,analyst,writer} running/done) followed
                              by the final result. Drives the UI progress tracker.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.config import settings
from backend.graph.pipeline import get_graph, run_research
from backend.models import Analysis, ResearchRequest, ResearchResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Equity Research Agent",
    description="LangGraph pipeline (Researcher -> Analyst -> Writer) over SEC, yfinance, and news.",
    version="1.0.0",
)

# Permissive CORS so the Next.js frontend (localhost:3000) can call the API,
# including the streaming endpoint.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Order of agent nodes, used to derive "next is running" transitions.
_STEPS = ("researcher", "analyst", "writer")


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

    mda = state.get("mda", {}) or {}
    news = state.get("news", {}) or {}
    metadata = {
        "chunks_indexed": state.get("chunks_indexed", 0),
        "sec_form": mda.get("form"),
        "filing_date": mda.get("filing_date"),
        "source_url": mda.get("source_url"),
        "news_count": len(news.get("results") or []),
        "chat_model": settings.CHAT_MODEL,
    }
    return ResearchResponse(
        ticker=ticker,
        company=state.get("company_name", ticker),
        report_markdown=state.get("report_markdown", ""),
        analysis=analysis,
        metadata=metadata,
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


@app.post("/research", response_model=ResearchResponse)
def research(request: ResearchRequest) -> ResearchResponse:
    ticker = request.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="`ticker` must not be empty.")

    try:
        state = run_research(ticker)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed for %s", ticker)
        raise HTTPException(status_code=500, detail=f"Research pipeline failed: {exc}")

    return _build_response(ticker, state)


@app.post("/research/stream")
def research_stream(request: ResearchRequest) -> StreamingResponse:
    """Stream live progress as each LangGraph node finishes, then the result.

    Uses LangGraph's ``stream(stream_mode="updates")``, which yields a
    ``{node_name: update}`` dict after each node completes — so the progress
    reported to the UI reflects the real pipeline, not a timer.
    """
    ticker = request.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="`ticker` must not be empty.")

    def event_gen() -> Iterator[str]:
        # The first node begins as soon as we start consuming the stream.
        yield _sse({"type": "step", "step": "researcher", "status": "running"})
        state: dict = {"ticker": ticker, "errors": []}
        try:
            for chunk in get_graph().stream(
                {"ticker": ticker, "errors": []}, stream_mode="updates"
            ):
                for node_name, update in chunk.items():
                    # Merge this node's update into the running state. `errors`
                    # is additive (matches the graph's reducer); others overwrite.
                    for key, value in (update or {}).items():
                        if key == "errors" and isinstance(value, list):
                            state.setdefault("errors", []).extend(value)
                        else:
                            state[key] = value

                    if node_name in _STEPS:
                        yield _sse({"type": "step", "step": node_name, "status": "done"})
                        i = _STEPS.index(node_name)
                        if i + 1 < len(_STEPS):
                            yield _sse(
                                {"type": "step", "step": _STEPS[i + 1], "status": "running"}
                            )

            result = _build_response(ticker, state)
            yield _sse({"type": "result", "data": result.model_dump()})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Streaming pipeline failed for %s", ticker)
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
