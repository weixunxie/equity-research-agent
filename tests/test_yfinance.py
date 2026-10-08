"""Normalization of yfinance output (no network: yf.Ticker is faked)."""
import pandas as pd
import pytest

from backend.tools import yfinance_tool


class FakeTicker:
    def __init__(self, info, quarterly=None, annual=None, history=None):
        self.info = info
        self.quarterly_income_stmt = quarterly
        self.income_stmt = annual
        self.quarterly_cashflow = None
        self._history = history

    def history(self, **_):
        return self._history


def statement(periods: dict[str, tuple[float, float]]) -> pd.DataFrame:
    """Columns are period-end dates, most recent first — like yfinance."""
    cols = sorted(periods, reverse=True)
    return pd.DataFrame(
        {pd.Timestamp(c): {"Total Revenue": periods[c][0], "Net Income": periods[c][1]} for c in cols}
    )


@pytest.fixture
def fake(monkeypatch):
    def install(**kwargs):
        monkeypatch.setattr(yfinance_tool.yf, "Ticker", lambda _symbol: FakeTicker(**kwargs))

    return install


def test_debt_to_equity_is_converted_from_percent_to_multiple(fake):
    fake(info={"debtToEquity": 195.0, "marketCap": 1e9, "trailingPE": 20.0})
    out = yfinance_tool.get_financials("TEST")
    assert out["balance"]["debt_to_equity"] == pytest.approx(1.95)
    assert out["debt_to_equity"] == pytest.approx(1.95)


def test_zero_gross_margin_means_not_applicable(fake):
    fake(info={"grossMargins": 0.0, "operatingMargins": 0.4, "marketCap": 1e9})
    prof = yfinance_tool.get_financials("BANK")["profitability"]
    assert prof["gross_margin"] is None
    assert prof["operating_margin"] == 0.4


def test_statement_series_is_oldest_first_and_drops_missing_periods(fake):
    quarterly = statement(
        {"2026-06-30": (120.0, 30.0), "2026-03-31": (110.0, 25.0), "2025-12-31": (float("nan"), 20.0)}
    )
    fake(info={"marketCap": 1e9}, quarterly=quarterly)
    rows = yfinance_tool.get_financials("TEST")["quarterly"]
    assert [r["period"] for r in rows] == ["2025-12-31", "2026-03-31", "2026-06-30"]
    assert "revenue" not in rows[0] and rows[0]["net_income"] == 20.0
    assert rows[-1] == {"period": "2026-06-30", "revenue": 120.0, "net_income": 30.0}


def test_upside_to_mean_target(fake):
    fake(info={"currentPrice": 200.0, "targetMeanPrice": 250.0, "marketCap": 1e9})
    assert yfinance_tool.get_financials("TEST")["analyst"]["upside_to_mean"] == pytest.approx(0.25)


def test_unknown_ticker_sets_error(fake):
    fake(info={})
    out = yfinance_tool.get_financials("NOPE")
    assert out["error"] and "NOPE" in out["error"]
    assert out["quarterly"] == [] and out["price_history"] == []


def test_peer_with_mismatched_currencies_is_dropped(monkeypatch):
    infos = {
        "ADR": {"marketCap": 5e11, "currency": "USD", "financialCurrency": "KRW"},
        "OK": {"marketCap": 5e11, "currency": "USD", "financialCurrency": "USD", "trailingPE": 12.0},
    }
    monkeypatch.setattr(yfinance_tool.yf, "Ticker", lambda s: FakeTicker(info=infos[s]))
    assert yfinance_tool._peer_snapshot("ADR") is None
    assert yfinance_tool._peer_snapshot("OK")["trailing_pe"] == 12.0
