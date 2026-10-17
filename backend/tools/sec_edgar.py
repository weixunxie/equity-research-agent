"""SEC EDGAR access: resolve tickers, locate the latest 10-K/10-Q, and extract
the Management's Discussion & Analysis (MD&A), Risk Factors (Item 1A), and
Business (Item 1) sections.

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
from functools import lru_cache
from typing import Any

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from backend.config import settings

logger = logging.getLogger(__name__)

# SEC filings are inline-XBRL .htm files; we intentionally parse them as HTML.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_REQUEST_DELAY = 0.2  # seconds between SEC requests (stay well under 10 req/s)
_COMPANY_INDEX_TTL = 24 * 3600
_company_index_cache: tuple[float, dict[str, dict[str, str]]] | None = None
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


def company_index() -> dict[str, dict[str, str]]:
    """Ticker -> {cik, title} for every SEC registrant, in the file's order
    (largest companies first). The source file is ~1MB and changes rarely, so
    it is fetched once a day rather than once per run. Raises on fetch failure."""
    global _company_index_cache
    now = time.monotonic()
    if _company_index_cache and now - _company_index_cache[0] < _COMPANY_INDEX_TTL:
        return _company_index_cache[1]
    data = _get(_COMPANY_TICKERS_URL).json()
    index = {
        str(row.get("ticker", "")).upper(): {
            "cik": str(row["cik_str"]).zfill(10),
            "title": row.get("title") or str(row.get("ticker", "")).upper(),
        }
        for row in data.values()
    }
    _company_index_cache = (now, index)
    return index


def lookup_ticker(index: dict[str, dict[str, str]], ticker: str) -> tuple[str, dict[str, str]] | None:
    """Find ``ticker`` in the SEC index, accepting the dotted share-class form
    ("BRK.B") for SEC's dashed one ("BRK-B"). Returns (sec_ticker, row)."""
    for candidate in dict.fromkeys((ticker, ticker.replace(".", "-"))):
        if candidate in index:
            return candidate, index[candidate]
    return None


def resolve_company(ticker: str) -> dict[str, str] | None:
    """Map a ticker to its zero-padded CIK and company title via SEC's
    company_tickers.json. Returns None if not found."""
    ticker = ticker.strip().upper()
    try:
        found = lookup_ticker(company_index(), ticker)
    except Exception as exc:  # noqa: BLE001 - network/parse failures are non-fatal
        logger.warning("Failed to fetch company_tickers.json: %s", exc)
        return None
    if found is None:
        logger.warning("Ticker %s not found in SEC company_tickers.json", ticker)
        return None
    return {**found[1], "ticker": ticker}


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


@lru_cache(maxsize=8)
def fetch_document_text(url: str) -> str:
    """Download a filing document and return its visible text (whitespace-collapsed).

    A filed document never changes, so the parsed text is kept for reuse — a
    10-K is several MB of HTML and takes a second or two to fetch and parse.
    """
    resp = _get(url)
    soup = BeautifulSoup(resp.content, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    # Separate block-level elements only. Inline-XBRL filings split words across
    # <span>/<ix:*> tags, so a blanket separator would yield "Ris k Factors".
    for tag in soup.find_all(_BLOCK_TAGS):
        tag.append(" ")
    return re.sub(r"\s+", " ", soup.get_text()).strip()


# Section boundaries by filing form: heading pattern -> the headings that end it.
# Patterns run against lower-cased, whitespace-collapsed filing text.
_APOS = r"['’`]?"
_SECTION_SPECS: dict[str, dict[str, tuple[str, tuple[str, ...]]]] = {
    "10-K": {
        "business": (
            r"item\s*1\s*[.:\-–—]?\s*business",
            (r"item\s*1a\s*[.:\-–—]?\s*risk\s+factors",),
        ),
        "risk_factors": (
            r"item\s*1a\s*[.:\-–—]?\s*risk\s+factors",
            (
                r"item\s*1b\s*[.:\-–—]?\s*unresolved",
                r"item\s*1c\s*[.:\-–—]?\s*cybersecurity",
                r"item\s*2\s*[.:\-–—]?\s*properties",
            ),
        ),
        "mda": (
            rf"item\s*7\s*[.:\-–—]?\s*management{_APOS}s\s+discussion",
            (
                r"item\s*7a\s*[.:\-–—]?\s*quantitative",
                r"item\s*8\s*[.:\-–—]?\s*financial\s+statements",
            ),
        ),
    },
    "10-Q": {
        "mda": (
            rf"item\s*2\s*[.:\-–—]?\s*management{_APOS}s\s+discussion",
            (
                r"item\s*3\s*[.:\-–—]?\s*quantitative",
                r"item\s*4\s*[.:\-–—]?\s*controls",
            ),
        ),
    },
    # Foreign private issuers (ADRs) file a 20-F instead of a 10-K.
    "20-F": {
        "business": (
            r"item\s*4\s*[.:\-–—]?\s*information\s+on\s+the\s+company",
            (
                r"item\s*4a\s*[.:\-–—]?\s*unresolved",
                r"item\s*5\s*[.:\-–—]?\s*operating\s+and\s+financial",
            ),
        ),
        "risk_factors": (
            r"(?:(?:item\s*)?3\.?\s*d\s*[.:\-–—]?\s*)?risk\s+factors",
            (r"item\s*4\s*[.:\-–—]?\s*information\s+on\s+the\s+company",),
        ),
        "mda": (
            r"item\s*5\s*[.:\-–—]?\s*operating\s+and\s+financial\s+review",
            (r"item\s*6\s*[.:\-–—]?\s*directors",),
        ),
    },
}
_BLOCK_TAGS = ["p", "div", "br", "tr", "td", "th", "li", "table", "h1", "h2", "h3", "h4", "h5"]
_ANNUAL_FORMS = ("10-K", "20-F")
_PERIODIC_FORMS = ("10-K", "10-Q", "20-F")
# A heading match is a cross-reference ("see Item 1A. Risk Factors, ...") rather
# than a section heading when it is led into or trailed like running prose.
_XREF_BEFORE_RE = re.compile(
    r"(\b(see|in|under|to|and|with|of|our|the)\s+|[“\"(,–—\-])\s*(part\s+[iv]+\s*,?\s*)?[“\"]?$"
)
_XREF_AFTER_RE = re.compile(r"\s*\.?\s*[”\",;)]")
_SECTION_CAPS = {"mda": 60_000, "risk_factors": 80_000, "business": 30_000}
_MIN_SECTION_CHARS = 1_500  # shorter matches are table-of-contents entries


def extract_section(text: str, form: str, section: str) -> str:
    """Extract one Item section (``mda`` / ``risk_factors`` / ``business``).

    A heading such as "Item 7. Management's Discussion" appears several times in
    a filing — in the table of contents, in cross-references, and once as the
    real section heading. Occurrences that read as cross-references or have no
    closing heading after them are skipped; each remaining one is cut at the
    next closing heading and the longest wins (a TOC entry yields a few hundred
    characters, the real section tens of thousands).
    """
    spec = _SECTION_SPECS.get(form.upper().split("/")[0], {}).get(section)
    if not text or not spec:
        return ""
    start_re, end_res = spec
    lower = text.lower()

    def headings(pattern: str, pos: int = 0):
        """Matches of ``pattern`` from ``pos`` that aren't cross-references."""
        for m in re.compile(pattern).finditer(lower, pos):
            if not _XREF_BEFORE_RE.search(lower[max(0, m.start() - 40) : m.start()]):
                yield m

    best = ""
    for m in headings(start_re):
        if section != "mda" and _XREF_AFTER_RE.match(lower, m.end()):
            continue
        ends = [
            e.start()
            for end_re in end_res
            if (e := next(headings(end_re, m.end()), None))
        ]
        if not ends:  # no closing heading after it: not a real section start
            continue
        candidate = text[m.start() : min(ends)].strip()
        if len(candidate) > len(best):
            best = candidate
    if len(best) < _MIN_SECTION_CHARS:
        return ""
    return best[: _SECTION_CAPS[section]]


def extract_mda(text: str, form: str = "10-K") -> str:
    """Extract the MD&A section, preferring Item-heading boundaries and falling
    back to a looser heading search for filings without standard Item labels."""
    section = extract_section(text, form, "mda")
    if not section:
        for other in _SECTION_SPECS:
            section = section or extract_section(text, other, "mda")
    return section or _extract_mda_loose(text)


def _extract_mda_loose(text: str) -> str:
    """Heading-only fallback: take the longest span that opens at a
    "Management's Discussion and Analysis" mention and closes at the next
    quantitative-disclosures / financial-statements / controls heading."""
    if not text:
        return ""
    lower = text.lower()
    end_res = (
        r"quantitative and qualitative disclosures? about market risk",
        r"item\s*8\.?\s*financial statements",
        r"item\s*4\.?\s*controls and procedures",
    )
    best = ""
    for m in re.finditer(rf"management{_APOS}s discussion and analysis", lower):
        end = min(len(text), m.start() + _SECTION_CAPS["mda"])
        for end_re in end_res:
            e = re.search(end_re, lower[m.end() : end])
            if e:
                end = min(end, m.end() + e.start())
        candidate = text[m.start() : end].strip()
        if len(candidate) > len(best):
            best = candidate
    return best if len(best) >= _MIN_SECTION_CHARS else ""


def _load_filing(cand: dict[str, Any]) -> str:
    try:
        return fetch_document_text(cand["url"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch filing %s: %s", cand["url"], exc)
        return ""


def get_filing_sections(
    ticker: str,
    start_date: str = "2023-01-01",
    end_date: str | None = None,
) -> dict[str, Any]:
    """Top-level entry point used by the Researcher node.

    * **MD&A** comes from the latest periodic report (10-K, 10-Q or 20-F), so
      it reflects the most recent period.
    * **Risk Factors** and **Business** come from the latest annual report
      (10-K, or 20-F for foreign issuers) — a 10-Q only carries updates to them.

    Tries the submissions API first (reliable primary document), then falls back
    to full-text search for the MD&A. Always returns a stable shape; on failure
    the text fields are empty and ``error`` explains why, so the pipeline can
    continue.
    """
    result: dict[str, Any] = {
        "ticker": ticker.upper(),
        "company": ticker.upper(),
        "cik": None,
        "form": None,
        "filing_date": None,
        "source_url": None,
        "mda_text": "",
        "annual_form": None,
        "annual_filing_date": None,
        "annual_source_url": None,
        "risk_factors_text": "",
        "business_text": "",
        "error": None,
    }

    company = resolve_company(ticker)
    cik = None
    if company:
        cik = company["cik"]
        result["cik"] = cik
        result["company"] = company["title"]

    latest = latest_filing(cik, _PERIODIC_FORMS) if cik else None
    annual = latest if latest and latest["form"] in _ANNUAL_FORMS else None
    if cik and annual is None:
        annual = latest_filing(cik, _ANNUAL_FORMS)

    # --- Risk Factors + Business from the latest annual report ---
    annual_text = _load_filing(annual) if annual else ""
    if annual_text:
        result["risk_factors_text"] = extract_section(
            annual_text, annual["form"], "risk_factors"
        )
        result["business_text"] = extract_section(annual_text, annual["form"], "business")
        if result["risk_factors_text"] or result["business_text"]:
            result.update(
                {
                    "annual_form": annual["form"],
                    "annual_filing_date": annual.get("filing_date"),
                    "annual_source_url": annual["url"],
                }
            )

    # --- MD&A: latest periodic report, then the 10-K, then full-text search ---
    candidates: list[dict[str, Any]] = []
    if latest:
        candidates.append(latest)
    if annual and annual is not latest:
        candidates.append(annual)

    def try_candidates(cands: list[dict[str, Any]]) -> bool:
        for cand in cands:
            text = annual_text if cand is annual else _load_filing(cand)
            mda = extract_mda(text, cand.get("form") or "10-K")
            if mda:
                result.update(
                    {
                        "form": cand.get("form"),
                        "filing_date": cand.get("filing_date"),
                        "source_url": cand["url"],
                        "mda_text": mda,
                    }
                )
                return True
        return False

    if try_candidates(candidates):
        return result

    # Full-text search is only consulted when the submissions API came up short.
    fallback: list[dict[str, Any]] = []
    for hit in search_filings(ticker, ("10-K", "10-Q"), start_date, end_date, cik=cik):
        url = _fts_doc_url(hit, cik)
        if url and all(url != c["url"] for c in candidates):
            fallback.append(
                {"form": hit.get("form"), "filing_date": hit.get("filing_date"), "url": url}
            )
    if try_candidates(fallback):
        return result

    result["error"] = (
        "Filings located but MD&A section could not be extracted."
        if candidates or fallback
        else "No 10-K/10-Q/20-F filings found for this ticker."
    )
    return result
