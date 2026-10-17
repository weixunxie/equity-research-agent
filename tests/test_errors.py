"""Raw provider errors stay in the server log; clients see a fixed reason.
The OpenAI 401 below is the real exception type, carrying a masked key."""
import json

import httpx
import openai
import pytest
import requests
import tavily.errors
from fastapi.testclient import TestClient

from backend import main
from backend.errors import describe_error
from backend.graph import pipeline
from backend.graph.nodes import analyst, writer
from backend.guard import RateLimiter, TTLCache
from backend.tools import tavily_news

SECRET = "Incorrect API key provided: sk-proj-****WXYZ"


def openai_401() -> openai.AuthenticationError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return openai.AuthenticationError(
        f"Error code: 401 - {{'error': {{'message': '{SECRET}'}}}}",
        response=httpx.Response(401, request=request),
        body=None,
    )


def http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"{status} for url https://x.example/?api_key=sk-SECRET", response=response)


@pytest.mark.parametrize(
    ("exc", "reason"),
    [
        (openai_401(), "the provider rejected the credentials"),
        (tavily.errors.InvalidAPIKeyError(SECRET), "the provider rejected the credentials"),
        (http_error(403), "the provider rejected the credentials"),
        (http_error(429), "the provider's usage limit was reached"),
        (tavily.errors.UsageLimitExceededError(SECRET), "the provider's usage limit was reached"),
        (requests.ReadTimeout(SECRET), "the provider timed out"),
        (requests.ConnectionError(SECRET), "the provider could not be reached"),
        (ValueError(SECRET), "an unexpected error occurred"),
    ],
)
def test_describe_error_never_echoes_the_message(exc, reason):
    assert describe_error(exc) == reason


class FailingModel:
    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        raise openai_401()


RESEARCH = {
    "company_name": "Test Corp",
    "mda": {"mda_text": "Revenue grew 10%.", "form": "10-Q"},
    "financials": {"valuation": {"market_cap": 1e9}},
    "peers": {"peers": []},
    "news": {"results": []},
    "chunks_indexed": 0,
    "errors": [],
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "validate_ticker", lambda _t: None)
    monkeypatch.setattr(main, "_cache", TTLCache(ttl=3600))
    monkeypatch.setattr(main, "_ip_limiter", RateLimiter(limit=10, window=3600))
    monkeypatch.setattr(main, "_global_limiter", RateLimiter(limit=100, window=86400))
    return TestClient(main.app)


def test_llm_401_is_not_leaked_by_a_degraded_run(monkeypatch, client):
    """Real Analyst and Writer, both hitting a 401 and falling back."""
    monkeypatch.setattr(pipeline, "researcher_node", lambda _s: RESEARCH)
    monkeypatch.setattr(main, "get_graph", pipeline.build_graph)
    monkeypatch.setattr(analyst, "query_filings", lambda *_a, **_k: [])
    monkeypatch.setattr(analyst, "get_chat_model", lambda **_: FailingModel())
    monkeypatch.setattr(writer, "get_chat_model", lambda **_: FailingModel())

    res = client.post("/research/stream", json={"ticker": "TEST"})
    assert res.status_code == 200
    assert "sk-proj" not in res.text and "Incorrect API key" not in res.text

    result = json.loads(res.text.strip().splitlines()[-1][5:])["data"]
    assert result["errors"] == [
        "Analyst: LLM synthesis failed (the provider rejected the credentials).",
        "Writer: LLM rendering failed (the provider rejected the credentials); used fallback template.",
    ]
    assert "the provider rejected the credentials" in result["analysis"]["thesis"]


def test_pipeline_crash_is_not_leaked(monkeypatch, client):
    class CrashingGraph:
        def stream(self, *_a, **_k):
            raise openai_401()
            yield  # pragma: no cover - makes this a generator

    def crash(_ticker):
        raise openai_401()

    monkeypatch.setattr(main, "get_graph", lambda: CrashingGraph())
    monkeypatch.setattr(main, "run_research", crash)

    res = client.post("/research/stream", json={"ticker": "TEST"})
    events = [json.loads(line[5:]) for line in res.text.splitlines() if line.startswith("data:")]
    assert events[-1] == {
        "type": "error",
        "message": "Research pipeline failed: the provider rejected the credentials.",
    }

    res = client.post("/research", json={"ticker": "TEST"})
    assert res.status_code == 500
    assert res.json()["detail"] == "Research pipeline failed: the provider rejected the credentials."


def test_tavily_401_is_not_leaked(monkeypatch):
    class FailingTavily:
        def __init__(self, api_key):
            pass

        def search(self, **_):
            raise tavily.errors.InvalidAPIKeyError(SECRET)

    monkeypatch.setattr(tavily_news.settings, "TAVILY_API_KEY", "tvly-key")
    monkeypatch.setattr(tavily, "TavilyClient", FailingTavily)
    out = tavily_news.get_recent_news("Test Corp")
    assert out["error"] == "Tavily search failed: the provider rejected the credentials."
