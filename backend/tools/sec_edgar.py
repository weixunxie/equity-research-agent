"""SEC EDGAR access: resolve tickers, locate the latest 10-K/10-Q, and extract
the Management's Discussion & Analysis (MD&A) section.

Two discovery paths:
  * **Primary** — the submissions API (``data.sec.gov``) returns a company's own
    filings with the exact ``primaryDocument`` for each, so we fetch the real
    10-K/10-Q body reliably.
  * **Fallback** — the full-text search API (``efts.sec.gov``) as specified.
    Note FTS hits point to whichever *sub-document* matched the query (often an
    exhibit/XBRL "R" file), so it's a fallback for body retrieval.

SEC requires a ``Name email@domain`` User-Agent (other formats get HTTP 403) and
rate-limits to ~10 req/s; we send the UA from settings and pace requests.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
import time
import warnings
from typing import Any

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from backend.config import settings

logger = logging.getLogger(__name__)

# SEC filings are inline-XBRL .htm files; we intentionally parse them as HTML.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_MAX_MDA_CHARS = 60_000
_REQUEST_DELAY = 0.2  # seconds between SEC requests (stay well under 10 req/s)
# Sub-documents that are never the primary 10-K/10-Q body (XBRL renders, exhibits).
_NON_PRIMARY_RE = re.compile(r"(^R\d+\.xml$|\.jpg$|\.png$|\.gif$|^ex)", re.IGNORECASE)


def _headers() -> dict[str, str]:
    # SEC requires a descriptive User-Agent; requests derives Host from the URL.
    return {
        "User-Agent": settings.SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
    }


def _get(url: str, **kwargs: Any) -> requests.Response:
    resp = requests.get(
        url, headers=_headers(), timeout=settings.REQUEST_TIMEOUT, **kwargs
    )
    time.sleep(_REQUEST_DELAY)
    resp.raise_for_status()
    return resp


def _doc_url(cik: str, accession: str, filename: str) -> str:
    """Build an archive URL: /edgar/data/<cik-int>/<accession-no-dashes>/<file>."""
    return (
        f"{settings.SEC_ARCHIVES_BASE}/edgar/data/"
        f"{str(int(cik))}/{accession.replace('-', '')}/{filename}"
    )


def resolve_company(ticker: str) -> dict[str, str] | None:
    """Map a ticker to its zero-padded CIK and company title via SEC's
    company_tickers.json. Returns None if not found."""
    ticker = ticker.strip().upper()
    try:
        data = _get(_COMPANY_TICKERS_URL).json()
    except Exception as exc:  # noqa: BLE001 - network/parse failures are non-fatal
        logger.warning("Failed to fetch company_tickers.json: %s", exc)
        return None

    for row in data.values():
        if str(row.get("ticker", "")).upper() == ticker:
            return {
                "cik": str(row["cik_str"]).zfill(10),
                "title": row.get("title", ticker),
                "ticker": ticker,
            }
    logger.warning("Ticker %s not found in SEC company_tickers.json", ticker)
    return None


def latest_filing(
    cik: str, forms: tuple[str, ...] = ("10-K", "10-Q")
) -> dict[str, Any] | None:
    """Return the most recent matching filing via the submissions API, including
    the exact primary document URL. This is the reliable path to the MD&A body."""
    url = settings.SEC_SUBMISSIONS_URL.format(cik=cik.zfill(10))
    try:
        recent = _get(url).json().get("filings", {}).get("recent", {})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Submissions API failed for CIK %s: %s", cik, exc)
        return None

    forms_list = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    dates = recent.get("filingDate", [])
    # Arrays are parallel and ordered most-recent-first.
    for i, form in enumerate(forms_list):
        if form in forms and i < len(primary_docs) and primary_docs[i]:
            return {
                "form": form,
                "filing_date": dates[i] if i < len(dates) else None,
                "accession": accessions[i],
                "primary_document": primary_docs[i],
                "url": _doc_url(cik, accessions[i], primary_docs[i]),
            }
    return None


def search_filings(
    ticker: str,
    forms: tuple[str, ...] = ("10-K", "10-Q"),
    start_date: str = "2023-01-01",
    end_date: str | None = None,
    cik: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Query the EDGAR full-text search API (efts.sec.gov/LATEST/search-index).

    Uses the real API contract: q + forms + startdt/enddt (the UI-only
    ``dateRange=custom`` param triggers HTTP 500 and is omitted). Results are
    filtered to the company's own CIK when known and de-duplicated by filing.
    """
    params: dict[str, Any] = {
        "q": ticker,
        "forms": ",".join(forms),
        "startdt": start_date,
        "enddt": end_date or dt.date.today().isoformat(),
    }
    try:
        payload = _get(settings.SEC_FTS_URL, params=params).json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("EDGAR full-text search failed for %s: %s", ticker, exc)
        return []

    results: list[dict[str, Any]] = []
    seen_accessions: set[str] = set()
    for hit in payload.get("hits", {}).get("hits", []):
        source = hit.get("_source", {})
        hit_ciks = [str(c).lstrip("0") for c in source.get("ciks", [])]
        if cik and cik.lstrip("0") not in hit_ciks:
            continue
        accession = hit.get("_id", "").split(":", 1)[0]
        if not accession or accession in seen_accessions:
            continue
        seen_accessions.add(accession)
        results.append(
            {
                "id": hit.get("_id", ""),
                "form": source.get("root_form") or source.get("file_type", ""),
                "filing_date": source.get("file_date", ""),
                "ciks": source.get("ciks", []),
                "display_names": source.get("display_names", []),
            }
        )
        if len(results) >= limit:
            break
    return results


def _fts_doc_url(hit: dict[str, Any], cik: str | None) -> str | None:
    """Build a document URL from an FTS hit, skipping non-primary sub-documents."""
    raw_id = hit.get("id", "")
    if ":" not in raw_id:
        return None
    accession, filename = raw_id.split(":", 1)
    if not filename or _NON_PRIMARY_RE.search(filename):
        return None
    resolved_cik = cik or (hit.get("ciks") or [""])[0]
    if not resolved_cik:
        return None
    return _doc_url(resolved_cik, accession, filename)


def fetch_document_text(url: str) -> str:
    """Download a filing document and return its visible text (whitespace-collapsed)."""
    resp = _get(url)
    soup = BeautifulSoup(resp.content, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()


def extract_mda(text: str) -> str:
    """Heuristically extract the MD&A section from filing text.

    Captures from the (last) 'Management's Discussion and Analysis' heading up to
    the next item boundary (Item 7A/8 for 10-K, Item 3/4 for 10-Q). Falls back to
    a fixed window if no clean end marker is found.
    """
    if not text:
        return ""

    lower = text.lower()
    starts = [m.start() for m in re.finditer(r"management['’]s discussion and analysis", lower)]
    if not starts:
        return ""
    start = starts[-1]  # skip the table-of-contents mention; take the real section

    end = len(text)
    for marker in (
        r"item\s*7a\.?\s*quantitative and qualitative",
        r"item\s*8\.?\s*financial statements",
        r"item\s*3\.?\s*quantitative and qualitative",
        r"item\s*4\.?\s*controls and procedures",
    ):
        m = re.search(marker, lower[start + 50 :])
        if m:
            end = min(end, start + 50 + m.start())

    section = text[start:end].strip()
    if len(section) < 200:  # extraction looked wrong; take a fixed window
        section = text[start : start + _MAX_MDA_CHARS].strip()
    return section[:_MAX_MDA_CHARS]


def get_mda(
    ticker: str,
    forms: tuple[str, ...] = ("10-K", "10-Q"),
    start_date: str = "2023-01-01",
    end_date: str | None = None,
) -> dict[str, Any]:
    """Top-level entry point used by the Researcher node.

    Tries the submissions API first (reliable primary document), then falls back
    to full-text search. Always returns a stable shape; on failure ``mda_text``
    is empty and ``error`` explains why, so the pipeline can continue.
    """
    result: dict[str, Any] = {
        "ticker": ticker.upper(),
        "company": ticker.upper(),
        "cik": None,
        "form": None,
        "filing_date": None,
        "source_url": None,
        "mda_text": "",
        "error": None,
    }

    company = resolve_company(ticker)
    cik = None
    if company:
        cik = company["cik"]
        result["cik"] = cik
        result["company"] = company["title"]

    # --- Primary path: submissions API -> exact primary document ---
    candidates: list[dict[str, Any]] = []
    if cik:
        filing = latest_filing(cik, forms)
        if filing:
            candidates.append(filing)

    # --- Fallback path: full-text search ---
    for hit in search_filings(ticker, forms, start_date, end_date, cik=cik):
        url = _fts_doc_url(hit, cik)
        if url:
            candidates.append(
                {"form": hit.get("form"), "filing_date": hit.get("filing_date"), "url": url}
            )

    if not candidates:
        result["error"] = "No 10-K/10-Q filings found for this ticker."
        return result

    for cand in candidates:
        try:
            text = fetch_document_text(cand["url"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to fetch filing %s: %s", cand["url"], exc)
            continue
        mda = extract_mda(text)
        if mda:
            result.update(
                {
                    "form": cand.get("form"),
                    "filing_date": cand.get("filing_date"),
                    "source_url": cand["url"],
                    "mda_text": mda,
                }
            )
            return result

    result["error"] = "Filings located but MD&A section could not be extracted."
    return result
