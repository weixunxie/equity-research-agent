"""Check that a ticker names a real security before any research runs on it.

A symbol is accepted when SEC EDGAR maps it to a CIK or yfinance returns price
history for it (the latter covers listings without SEC filings, such as
foreign exchanges). When neither resolves, the caller gets an
``UnknownTickerError`` carrying the closest SEC ticker as a suggestion, so a
typo like "APPL" comes back as "Did you mean AAPL?" instead of a report built
from nothing.
"""
from __future__ import annotations

import logging

import yfinance as yf

from backend.tools.sec_edgar import company_index, lookup_ticker

logger = logging.getLogger(__name__)


class UnknownTickerError(LookupError):
    """Neither SEC EDGAR nor yfinance recognizes the symbol."""

    def __init__(self, ticker: str, suggestion: str | None = None) -> None:
        self.ticker = ticker
        self.suggestion = suggestion
        message = f"Unknown ticker '{ticker}'."
        if suggestion:
            message += f" Did you mean {suggestion}?"
        super().__init__(message)


class TickerCheckUnavailable(RuntimeError):
    """The symbol couldn't be verified because the SEC ticker list is
    unreachable — an outage, not evidence that the ticker is wrong."""


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance counting an adjacent swap ("MSTF" -> "MSFT") as one
    edit (optimal string alignment)."""
    prev2: list[int] = []
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        prev2, prev = prev, cur
    return prev[-1]


def suggest_ticker(ticker: str, tickers: list[str]) -> str | None:
    """The closest ticker within one edit (two for symbols longer than four
    characters). ``tickers`` is in SEC order, largest companies first, so a tie
    goes to the better-known name: "APPL" suggests AAPL rather than APPS."""
    max_distance = 1 if len(ticker) <= 4 else 2
    best: tuple[int, str] | None = None
    for candidate in tickers:
        if abs(len(candidate) - len(ticker)) > max_distance:
            continue
        distance = _edit_distance(ticker, candidate)
        if distance <= max_distance and (best is None or distance < best[0]):
            best = (distance, candidate)
            if distance == 1:
                break  # nothing closer than one edit remains for an unknown symbol
    return best[1] if best else None


def _has_price_history(ticker: str) -> bool:
    for symbol in dict.fromkeys((ticker, ticker.replace(".", "-"))):
        try:
            hist = yf.Ticker(symbol).history(period="5d")
        except Exception as exc:  # noqa: BLE001 - yfinance raises for some unknown symbols
            logger.info("yfinance history failed for %s: %s", symbol, exc)
            continue
        if hist is not None and not hist.empty:
            return True
    return False


def validate_ticker(ticker: str) -> None:
    """Return if ``ticker`` resolves; otherwise raise ``UnknownTickerError``
    (with a suggestion when one is close) or ``TickerCheckUnavailable``."""
    try:
        index = company_index()
    except Exception as exc:  # noqa: BLE001
        logger.warning("SEC ticker list unavailable for validation: %s", exc)
        index = None

    if index is not None and lookup_ticker(index, ticker):
        return
    if _has_price_history(ticker):
        return
    if index is None:
        raise TickerCheckUnavailable(
            f"Couldn't verify ticker '{ticker}' right now. Please try again shortly."
        )
    raise UnknownTickerError(ticker, suggest_ticker(ticker, list(index)))
