"""API behaviour with the pipeline faked: validation, streaming event order,
caching and rate limiting. No network or LLM calls."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.guard import RateLimiter, TTLCache

ANALYSIS = {
    "thesis": "t",
    "stance": "neutral",
    "stance_rationale": "r",
    "business_overview": "b",
    "bull_case": ["up"],
    "bear_case": ["down"],
    "catalysts": [],
    "key_risks": [{"title": "Risk", "detail": "d", "severity": "high"}],
    "valuation_view": "v",
    "recent_sentiment": {"label": "mixed", "summary": "s", "notable_headlines": []},
    "financial_summary": {
        "revenue_trend": "a",
        "profitability_trend": "b",
        "balance_sheet": "c",
        "commentary": "d",
    },
}
RESEARCH = {
    "company_name": "Test Corp",
    "mda": {"form": "10-Q", "filing_date": "2026-08-01", "source_url": "https://sec.gov/x", "mda_text": "m"},
    "financials": {"ticker": "TEST", "valuation": {"market_cap": 1e9}},
    "peers": {"peers": [{"ticker": "PEER"}], "basis": "basis"},
    "news": {"results": [{"title": "Headline", "url": "https://n.example/a", "content": " body  text "}]},
    "chunks_indexed": 0,
    "errors": ["News: partial"],
}


class FakeGraph:
    def __init__(self, analyst_errors=None):
        self.calls = 0
        self.analyst_errors = analyst_errors or []

    def stream(self, _state, stream_mode):
        assert stream_mode == ["updates", "messages"]
        self.calls += 1
        yield "updates", {"researcher": RESEARCH}
        # Structured-output chatter from the Analyst must not reach the client.
        yield "messages", (SimpleNamespace(content="{json"), {"langgraph_node": "analyst"})
        yield "updates", {"analyst": {"analysis": ANALYSIS, "errors": self.analyst_errors}}
        for text in ("# Test", " report"):
            yield "messages", (SimpleNamespace(content=text), {"langgraph_node": "writer"})
        yield "updates", {"writer": {"report_markdown": "# Test report"}}


@pytest.fixture
def api(monkeypatch):
    graph = FakeGraph()
    monkeypatch.setattr(main, "get_graph", lambda: graph)
    monkeypatch.setattr(main, "validate_ticker", lambda _t: None)  # see test_ticker_check
    monkeypatch.setattr(main, "_cache", TTLCache(ttl=3600))
    monkeypatch.setattr(main, "_ip_limiter", RateLimiter(limit=2, window=3600))
    monkeypatch.setattr(main, "_global_limiter", RateLimiter(limit=100, window=86400))
    return SimpleNamespace(client=TestClient(main.app), graph=graph)


def stream(client, ticker="TEST", **body):
    res = client.post("/research/stream", json={"ticker": ticker, **body})
    events = [json.loads(line[5:]) for line in res.text.splitlines() if line.startswith("data:")]
    return res, events


def test_stream_emits_events_in_pipeline_order(api):
    res, events = stream(api.client, "test")
    assert res.status_code == 200
    assert [e["type"] for e in events] == [
        "step", "data", "step", "step", "analysis", "step", "step", "token", "token", "step", "result",
    ]
    assert [(e["step"], e["status"]) for e in events if e["type"] == "step"] == [
        ("researcher", "running"), ("researcher", "done"),
        ("analyst", "running"), ("analyst", "done"),
        ("writer", "running"), ("writer", "done"),
    ]
    assert "".join(e["text"] for e in events if e["type"] == "token") == "# Test report"

    data = events[1]["data"]
    assert data["ticker"] == "TEST" and data["company"] == "Test Corp"
    assert data["peers"] == [{"ticker": "PEER"}]
    assert data["news"][0]["snippet"] == "body text"
    assert data["sources"][0]["kind"] == "filing"

    result = events[-1]["data"]
    assert result["report_markdown"] == "# Test report"
    assert result["analysis"]["key_risks"][0]["severity"] == "high"
    assert result["errors"] == ["News: partial"]
    assert result["metadata"]["cached"] is False


def test_second_request_is_served_from_cache(api):
    stream(api.client)
    _, events = stream(api.client)
    assert api.graph.calls == 1
    assert [e["type"] for e in events] == ["result"]
    assert events[0]["data"]["metadata"]["cached"] is True

    stream(api.client, refresh=True)
    assert api.graph.calls == 2


def test_degraded_runs_are_not_cached(api):
    api.graph.analyst_errors = ["Analyst: LLM synthesis failed (boom)."]
    stream(api.client)
    stream(api.client)
    assert api.graph.calls == 2


def test_rate_limit_counts_runs_but_not_cache_hits(api):
    assert stream(api.client, "AAA")[0].status_code == 200
    assert stream(api.client, "AAA")[0].status_code == 200  # cache hit: free
    assert stream(api.client, "BBB")[0].status_code == 200
    res = api.client.post("/research/stream", json={"ticker": "CCC"})
    assert res.status_code == 429
    assert int(res.headers["retry-after"]) > 0
    assert "hourly limit" in res.json()["detail"]
    assert api.graph.calls == 2


def test_rate_limit_is_per_client_using_the_proxy_appended_address(api):
    def call(ticker, forwarded):
        return api.client.post(
            "/research/stream", json={"ticker": ticker}, headers={"X-Forwarded-For": forwarded}
        ).status_code

    assert call("AAA", "1.1.1.1") == 200
    assert call("BBB", "1.1.1.1") == 200
    assert call("CCC", "1.1.1.1") == 429
    assert call("CCC", "2.2.2.2") == 200
    # A forged left-hand entry doesn't buy a fresh budget.
    assert call("DDD", "9.9.9.9, 1.1.1.1") == 429


@pytest.mark.parametrize("ticker", ["", "   ", "TOOLONGTICKER", "AAPL; DROP", "../etc", "A B"])
def test_invalid_tickers_are_rejected(api, ticker):
    res = api.client.post("/research/stream", json={"ticker": ticker})
    assert res.status_code in (400, 422)
    assert api.graph.calls == 0


@pytest.mark.parametrize("ticker", ["aapl", "BRK-B", "BF.B", " nvda "])
def test_valid_tickers_are_accepted(api, ticker):
    assert stream(api.client, ticker)[0].status_code == 200


def test_blocking_endpoint_shares_cache_with_stream(api, monkeypatch):
    stream(api.client)
    monkeypatch.setattr(main, "run_research", lambda _t: pytest.fail("pipeline should not run"))
    res = api.client.post("/research", json={"ticker": "TEST"})
    assert res.status_code == 200
    assert res.json()["metadata"]["cached"] is True


def test_cors_allows_listed_and_pattern_origins_only():
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://equity-research-agent-six.vercel.app"],
        allow_origin_regex=r"https://equity-research-agent-[a-z0-9]+-stephanie-xie-s-projects\.vercel\.app",
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    client = TestClient(app)

    def allowed(origin):
        res = client.options(
            "/research/stream",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        return res.headers.get("access-control-allow-origin") == origin

    assert allowed("https://equity-research-agent-six.vercel.app")
    assert allowed("https://equity-research-agent-5869k6knw-stephanie-xie-s-projects.vercel.app")
    assert not allowed("https://evil.example")
    assert not allowed("https://equity-research-agent-six.vercel.app.evil.example")
