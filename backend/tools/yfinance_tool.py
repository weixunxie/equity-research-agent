"""yfinance-backed fundamentals: PE, quarterly revenue & net income,
debt-to-equity, and free cash flow."""
from __future__ import annotations

import logging
import math
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)


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
    """Pull the last ``n`` quarterly values for a row from a yfinance statement
    DataFrame (columns are period-end dates, most recent first)."""
    points: list[dict[str, Any]] = []
    if df is None or getattr(df, "empty", True):
        return points
    if row_label not in df.index:
        return points
    series = df.loc[row_label]
    for period, value in list(series.items())[:n]:
        points.append(
            {
                "period": str(getattr(period, "date", lambda: period)()),
                "value": _clean(value),
            }
        )
    return points


def get_financials(ticker: str) -> dict[str, Any]:
    """Fetch the fundamentals the Analyst node summarizes.

    Always returns a stable shape; individual fields are ``None`` when a metric
    is unavailable. A top-level ``error`` is set if the ticker can't be loaded.
    """
    out: dict[str, Any] = {
        "ticker": ticker.upper(),
        "currency": None,
        "pe_ratio": None,
        "revenue_quarterly": [],
        "net_income_quarterly": [],
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

    out["currency"] = info.get("currency") or info.get("financialCurrency")
    out["pe_ratio"] = _clean(info.get("trailingPE"))
    out["market_cap"] = _clean(info.get("marketCap"))
    # yfinance reports debtToEquity as a percentage (e.g. 195.0 == 1.95x).
    out["debt_to_equity"] = _clean(info.get("debtToEquity"))
    out["free_cash_flow"] = _clean(info.get("freeCashflow"))

    # Quarterly income statement (revenue + net income).
    try:
        income = tk.quarterly_income_stmt
    except Exception as exc:  # noqa: BLE001
        logger.warning("quarterly_income_stmt failed for %s: %s", ticker, exc)
        income = None

    out["revenue_quarterly"] = _series_last_n(income, "Total Revenue", 4)
    out["net_income_quarterly"] = _series_last_n(income, "Net Income", 4)

    # Fallback for FCF from the cash-flow statement when .info lacks it.
    if out["free_cash_flow"] is None:
        try:
            cf = tk.quarterly_cashflow
            if cf is not None and not cf.empty and "Free Cash Flow" in cf.index:
                out["free_cash_flow"] = _clean(cf.loc["Free Cash Flow"].iloc[0])
        except Exception as exc:  # noqa: BLE001
            logger.warning("quarterly_cashflow failed for %s: %s", ticker, exc)

    if (
        out["pe_ratio"] is None
        and not out["revenue_quarterly"]
        and out["market_cap"] is None
    ):
        out["error"] = (
            f"No fundamentals returned for '{ticker}'. "
            "Check the ticker symbol and network access."
        )
    return out
