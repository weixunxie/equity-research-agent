"""yfinance-backed market data: company profile, price history, valuation,
profitability, growth, balance sheet, analyst targets, quarterly/annual income
statement series, and a small peer set for relative valuation."""
from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)

# Income-statement rows surfaced as time series (output key -> yfinance row label).
_STATEMENT_ROWS = {
    "revenue": "Total Revenue",
    "gross_profit": "Gross Profit",
    "operating_income": "Operating Income",
    "net_income": "Net Income",
}
_PEER_COUNT = 4
_PEER_CANDIDATES = 6  # per source (industry + sector)


def _clean(value: Any) -> float | None:
    """Coerce to float, mapping NaN/inf/None to None."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _series_last_n(df: Any, row_label: str, n: int = 4) -> list[dict[str, Any]]:
    """Pull the last ``n`` values for a row from a yfinance statement DataFrame
    (columns are period-end dates, most recent first). Periods with no reported
    value are dropped."""
    points: list[dict[str, Any]] = []
    if df is None or getattr(df, "empty", True):
        return points
    if row_label not in df.index:
        return points
    series = df.loc[row_label]
    for period, value in list(series.items())[:n]:
        cleaned = _clean(value)
        if cleaned is None:
            continue
        points.append(
            {
                "period": str(getattr(period, "date", lambda: period)()),
                "value": cleaned,
            }
        )
    return points


def _statement_series(df: Any, n: int) -> list[dict[str, Any]]:
    """Merge the tracked income-statement rows into one list of per-period dicts,
    oldest first (chart order)."""
    by_period: dict[str, dict[str, Any]] = {}
    for key, label in _STATEMENT_ROWS.items():
        for point in _series_last_n(df, label, n):
            by_period.setdefault(point["period"], {"period": point["period"]})[key] = point[
                "value"
            ]
    return [by_period[p] for p in sorted(by_period)]


def _price_history(tk: Any) -> list[dict[str, Any]]:
    """One year of daily closes as ``[{date, close}]``, oldest first."""
    hist = tk.history(period="1y", interval="1d", auto_adjust=True)
    if hist is None or hist.empty or "Close" not in hist:
        return []
    points: list[dict[str, Any]] = []
    for ts, close in hist["Close"].items():
        value = _clean(close)
        if value is not None:
            points.append({"date": ts.date().isoformat(), "close": round(value, 2)})
    return points


def get_financials(ticker: str) -> dict[str, Any]:
    """Fetch the market data the Analyst node and the dashboard consume.

    Always returns a stable shape; individual fields are ``None`` (or empty
    lists) when a metric is unavailable. A top-level ``error`` is set if the
    ticker can't be loaded. Ratios (margins, growth, ROE, debt/equity) are plain
    fractions/multiples — 0.25 means 25%, debt/equity 1.95 means 1.95x.
    """
    out: dict[str, Any] = {
        "ticker": ticker.upper(),
        "currency": None,
        "profile": {},
        "price": {},
        "valuation": {},
        "profitability": {},
        "growth": {},
        "balance": {},
        "analyst": {},
        "quarterly": [],
        "annual": [],
        "price_history": [],
        # Flat aliases kept for the original consumers.
        "pe_ratio": None,
        "debt_to_equity": None,
        "free_cash_flow": None,
        "market_cap": None,
        "error": None,
    }

    try:
        tk = yf.Ticker(ticker)
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"Failed to initialize yfinance ticker: {exc}"
        return out

    # .info is occasionally flaky; never let it sink the whole call.
    info: dict[str, Any] = {}
    try:
        info = tk.info or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("yfinance .info failed for %s: %s", ticker, exc)

    def num(key: str) -> float | None:
        return _clean(info.get(key))

    out["currency"] = info.get("currency") or info.get("financialCurrency")
    out["profile"] = {
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "website": info.get("website"),
        "employees": num("fullTimeEmployees"),
        "summary": info.get("longBusinessSummary"),
    }
    current = num("currentPrice") or num("regularMarketPrice")
    out["price"] = {
        "current": current,
        "previous_close": num("previousClose"),
        # regularMarketChangePercent is already in percent units (0.6 == 0.6%).
        "change_pct": num("regularMarketChangePercent"),
        "fifty_two_week_high": num("fiftyTwoWeekHigh"),
        "fifty_two_week_low": num("fiftyTwoWeekLow"),
        "beta": num("beta"),
    }
    out["valuation"] = {
        "market_cap": num("marketCap"),
        "enterprise_value": num("enterpriseValue"),
        "trailing_pe": num("trailingPE"),
        "forward_pe": num("forwardPE"),
        "peg": num("trailingPegRatio") or num("pegRatio"),
        "price_to_sales": num("priceToSalesTrailing12Months"),
        "price_to_book": num("priceToBook"),
        "ev_to_ebitda": num("enterpriseToEbitda"),
        "ev_to_revenue": num("enterpriseToRevenue"),
    }
    out["profitability"] = {
        # Yahoo reports 0 where gross margin doesn't apply (banks, insurers).
        "gross_margin": num("grossMargins") or None,
        "operating_margin": num("operatingMargins"),
        "net_margin": num("profitMargins"),
        "return_on_equity": num("returnOnEquity"),
        "trailing_eps": num("trailingEps"),
        "forward_eps": num("forwardEps"),
    }
    out["growth"] = {
        "revenue_yoy": num("revenueGrowth"),
        "earnings_yoy": num("earningsGrowth"),
        "revenue_ttm": num("totalRevenue"),
    }
    # yfinance reports debtToEquity as a percentage (195.0 == 1.95x); normalize
    # it to a multiple so downstream consumers can't misread it.
    dte_pct = num("debtToEquity")
    out["balance"] = {
        "total_cash": num("totalCash"),
        "total_debt": num("totalDebt"),
        "debt_to_equity": None if dte_pct is None else round(dte_pct / 100, 4),
        "current_ratio": num("currentRatio"),
        "free_cash_flow": num("freeCashflow"),
        "operating_cash_flow": num("operatingCashflow"),
    }
    target_mean = num("targetMeanPrice")
    out["analyst"] = {
        "target_mean": target_mean,
        "target_high": num("targetHighPrice"),
        "target_low": num("targetLowPrice"),
        "recommendation": info.get("recommendationKey"),
        "analyst_count": num("numberOfAnalystOpinions"),
        "upside_to_mean": (
            round(target_mean / current - 1, 4) if target_mean and current else None
        ),
    }

    try:
        out["quarterly"] = _statement_series(tk.quarterly_income_stmt, 5)
    except Exception as exc:  # noqa: BLE001
        logger.warning("quarterly_income_stmt failed for %s: %s", ticker, exc)
    try:
        out["annual"] = _statement_series(tk.income_stmt, 4)
    except Exception as exc:  # noqa: BLE001
        logger.warning("income_stmt failed for %s: %s", ticker, exc)
    try:
        out["price_history"] = _price_history(tk)
    except Exception as exc:  # noqa: BLE001
        logger.warning("price history failed for %s: %s", ticker, exc)

    # Fallback for FCF from the cash-flow statement when .info lacks it.
    if out["balance"]["free_cash_flow"] is None:
        try:
            cf = tk.quarterly_cashflow
            if cf is not None and not cf.empty and "Free Cash Flow" in cf.index:
                out["balance"]["free_cash_flow"] = _clean(cf.loc["Free Cash Flow"].iloc[0])
        except Exception as exc:  # noqa: BLE001
            logger.warning("quarterly_cashflow failed for %s: %s", ticker, exc)

    out["pe_ratio"] = out["valuation"]["trailing_pe"]
    out["market_cap"] = out["valuation"]["market_cap"]
    out["debt_to_equity"] = out["balance"]["debt_to_equity"]
    out["free_cash_flow"] = out["balance"]["free_cash_flow"]

    if out["pe_ratio"] is None and not out["quarterly"] and out["market_cap"] is None:
        out["error"] = (
            f"No fundamentals returned for '{ticker}'. "
            "Check the ticker symbol and network access."
        )
    return out


def _peer_snapshot(symbol: str) -> dict[str, Any] | None:
    try:
        info = yf.Ticker(symbol).info or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("peer lookup failed for %s: %s", symbol, exc)
        return None
    market_cap = _clean(info.get("marketCap"))
    if not market_cap:
        return None
    # Listings quoted in one currency but reporting in another (many ADRs) come
    # back with multiples that mix the two, so they can't be compared.
    if info.get("currency") != info.get("financialCurrency"):
        return None
    return {
        "ticker": symbol,
        "name": info.get("shortName") or info.get("longName") or symbol,
        "market_cap": market_cap,
        "trailing_pe": _clean(info.get("trailingPE")),
        "forward_pe": _clean(info.get("forwardPE")),
        "ev_to_ebitda": _clean(info.get("enterpriseToEbitda")),
        "price_to_sales": _clean(info.get("priceToSalesTrailing12Months")),
        "gross_margin": _clean(info.get("grossMargins")) or None,
        "operating_margin": _clean(info.get("operatingMargins")),
        "revenue_yoy": _clean(info.get("revenueGrowth")),
    }


def get_peers(ticker: str, count: int = _PEER_COUNT) -> dict[str, Any]:
    """Pick comparable companies for relative valuation.

    Candidates are the largest names in the ticker's industry and sector
    (Yahoo's own classification); the ``count`` closest in market cap are kept,
    so a mega-cap is compared with other mega-caps rather than with micro-caps
    that merely share its industry label.
    """
    ticker = ticker.upper()
    out: dict[str, Any] = {"peers": [], "basis": None, "error": None}
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"Peer lookup failed: {exc}"
        return out

    own_cap = _clean(info.get("marketCap"))
    candidates: list[str] = []
    for cls, key in ((yf.Industry, info.get("industryKey")), (yf.Sector, info.get("sectorKey"))):
        if not key:
            continue
        try:
            top = cls(key).top_companies
            if top is not None and not top.empty:
                candidates.extend(str(s) for s in top.index[: _PEER_CANDIDATES + 1])
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s lookup failed for %s: %s", cls.__name__, key, exc)

    symbols = [s for s in dict.fromkeys(candidates) if s.upper() != ticker]
    if not symbols or not own_cap:
        out["error"] = "No comparable companies found for this ticker."
        return out

    with ThreadPoolExecutor(max_workers=8) as pool:
        snapshots = [s for s in pool.map(_peer_snapshot, symbols) if s]

    snapshots.sort(key=lambda s: abs(math.log(s["market_cap"] / own_cap)))
    out["peers"] = snapshots[:count]
    out["basis"] = (
        f"Largest {info.get('industry') or 'industry'} / {info.get('sector') or 'sector'} "
        "companies by Yahoo Finance classification, closest in market cap."
    )
    if not out["peers"]:
        out["error"] = "No comparable companies found for this ticker."
    return out
