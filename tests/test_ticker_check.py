"""Ticker validation and the no-source-data path. SEC's ticker list, yfinance
and the LLM are faked, so nothing touches the network."""
import json
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.graph import pipeline
from backend.graph.nodes import analyst, writer
from backend.guard import RateLimiter, TTLCache
from backend.tools import ticker_check

# In SEC file order: largest companies first.
SEC_INDEX = {
    "AAPL": {"cik": "0000320193", "title": "Apple Inc."},
    "MSFT": {"cik": "0000789019", "title": "MICROSOFT CORP"},
    "BRK-B": {"cik": "0001067983", "title": "BERKSHIRE HATHAWAY INC"},
    "APPS": {"cik": "0001437491", "title": "Digital Turbine, Inc."},
}
PRICED = pd.DataFrame({"Close": [100.0, 101.0]})


class FakeYfTicker:
    """Only symbols in ``listed`` have price history, as with yfinance."""

    listed: set[str] = set()

    def __init__(self, symbol):
        self.symbol = symbol

    def history(self, **_):
        return PRICED if self.symbol in self.listed else pd.DataFrame()


@pytest.fixture
def sources(monkeypatch):
    state = SimpleNamespace(index=SEC_INDEX, listed=set())

    def company_index():
        if state.index is None:
            raise ConnectionError("sec.gov unreachable")
        return state.index

    monkeypatch.setattr(ticker_check, "company_index", company_index)
    monkeypatch.setattr(FakeYfTicker, "listed", state.listed)
    monkeypatch.setattr(ticker_check.yf, "Ticker", FakeYfTicker)
    return state


@pytest.fixture
def client(monkeypatch, sources):
    monkeypatch.setattr(main, "get_graph", lambda: pytest.fail("pipeline must not run"))
    monkeypatch.setattr(main, "_cache", TTLCache(ttl=3600))
    monkeypatch.setattr(main, "_ip_limiter", RateLimiter(limit=1, window=3600))
    monkeypatch.setattr(main, "_global_limiter", RateLimiter(limit=100, window=86400))
    return TestClient(main.app)


# --- validation -----------------------------------------------------------


@pytest.mark.parametrize("path", ["/research", "/research/stream"])
def test_unknown_ticker_is_a_404_and_runs_nothing(client, path):
    res = client.post(path, json={"ticker": "qzxv"})
    assert res.status_code == 404
    assert res.json()["detail"] == {
        "code": "unknown_ticker",
        "message": "Unknown ticker 'QZXV'.",
        "ticker": "QZXV",
        "suggestion": None,
    }


@pytest.mark.parametrize("path", ["/research", "/research/stream"])
def test_typo_suggests_the_closest_ticker(client, path):
    res = client.post(path, json={"ticker": "APPL"})
    assert res.status_code == 404
    detail = res.json()["detail"]
    assert detail["message"] == "Unknown ticker 'APPL'. Did you mean AAPL?"
    assert detail["suggestion"] == "AAPL"


def test_unknown_tickers_do_not_use_up_the_rate_limit(client):
    for _ in range(3):
        assert client.post("/research/stream", json={"ticker": "APPL"}).status_code == 404
    assert main._ip_limiter.retry_after("testclient") == 0


def test_sec_listed_ticker_passes_without_asking_yfinance(sources, monkeypatch):
    monkeypatch.setattr(ticker_check.yf, "Ticker", lambda _s: pytest.fail("yfinance not needed"))
    ticker_check.validate_ticker("MSFT")
    ticker_check.validate_ticker("BRK.B")  # dotted share class maps to SEC's BRK-B


def test_ticker_with_price_history_but_no_sec_listing_passes(sources):
    sources.listed.add("7203.T")
    ticker_check.validate_ticker("7203.T")


def test_sec_outage_is_not_reported_as_an_unknown_ticker(sources):
    sources.index = None
    with pytest.raises(ticker_check.TickerCheckUnavailable):
        ticker_check.validate_ticker("QZXV")
    sources.listed.add("AAPL")
    ticker_check.validate_ticker("AAPL")  # yfinance alone still vouches for it


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("APPL", "AAPL"),  # ties with APPS; the larger company wins
        ("MSTF", "MSFT"),  # transposition counts as one edit
        ("MSFTT", "MSFT"),
        ("BRKB", "BRK-B"),
        ("QZXV", None),
    ],
)
def test_suggest_ticker(typed, expected):
    assert ticker_check.suggest_ticker(typed, list(SEC_INDEX)) == expected


# --- no source data -------------------------------------------------------

EMPTY_RESEARCH = {
    "company_name": "Ghost Corp",
    "mda": {"mda_text": "", "risk_factors_text": "", "business_text": "", "error": "No filings."},
    "financials": {"valuation": {"market_cap": None}, "quarterly": [], "annual": [], "price_history": []},
    "peers": {"peers": []},
    "news": {"results": [{"title": "Rumour", "url": "https://n.example/r"}]},
    "chunks_indexed": 0,
    "errors": ["SEC filings: No filings.", "Financials: No fundamentals."],
}


@pytest.fixture
def no_llm(monkeypatch):
    def refuse(**_):
        pytest.fail("the LLM must not be called without source data")

    monkeypatch.setattr(analyst, "get_chat_model", refuse)
    monkeypatch.setattr(writer, "get_chat_model", refuse)


def test_has_source_data():
    assert not analyst.has_source_data(EMPTY_RESEARCH)
    assert analyst.has_source_data({**EMPTY_RESEARCH, "mda": {"mda_text": "Revenue grew."}})
    assert analyst.has_source_data({**EMPTY_RESEARCH, "financials": {"valuation": {"market_cap": 1e9}}})
    assert analyst.has_source_data(
        {**EMPTY_RESEARCH, "financials": {"annual": [{"period": "2025-12-31", "revenue": 1.0}]}}
    )


def test_no_data_run_streams_no_thesis(monkeypatch, sources, no_llm):
    """Real Analyst and Writer nodes behind a Researcher that found nothing."""
    sources.listed.add("GHST")
    monkeypatch.setattr(pipeline, "researcher_node", lambda _s: EMPTY_RESEARCH)
    monkeypatch.setattr(main, "get_graph", pipeline.build_graph)
    monkeypatch.setattr(main, "_cache", TTLCache(ttl=3600))
    monkeypatch.setattr(main, "_ip_limiter", RateLimiter(limit=10, window=3600))

    res = TestClient(main.app).post("/research/stream", json={"ticker": "GHST"})
    events = [json.loads(line[5:]) for line in res.text.splitlines() if line.startswith("data:")]

    assert res.status_code == 200
    assert not [e for e in events if e["type"] == "token"]
    data = next(e for e in events if e["type"] == "data")["data"]
    assert data["insufficient_data"] is True  # known before the Analyst runs
    assert next(e for e in events if e["type"] == "analysis")["data"] is None

    result = events[-1]
    assert result["type"] == "result"
    report = result["data"]
    assert report["analysis"] is None
    assert report["insufficient_data"] is True
    assert report["report_markdown"] == "# Ghost Corp (GHST)\n\nNot enough source data to form a view."
    assert any("Not enough source data" in e for e in report["errors"])
    assert main._cache.get("GHST") is None  # retry later rather than serve the empty run
