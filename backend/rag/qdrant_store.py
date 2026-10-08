"""Qdrant vector store for the `sec_filings` collection.

Indexes filing sections (MD&A, Risk Factors, Business) per ticker and supports
semantic queries filtered by ticker and section, used by the Analyst node. All operations degrade gracefully: if Qdrant or OpenAI is
unreachable, indexing returns 0 and queries return an empty list so the agent
pipeline keeps running. If the configured server itself is unreachable, an
in-process store takes over (see ``get_client``).
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from functools import lru_cache
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from backend.config import settings
from backend.rag.chunking import chunk_text
from backend.rag.embeddings import embed_query, embed_texts

logger = logging.getLogger(__name__)

COLLECTION = settings.QDRANT_COLLECTION
_UPSERT_BATCH = 64  # points per upsert request


@lru_cache
def get_client() -> QdrantClient:
    """Return the configured Qdrant client, or an in-process one if the
    configured server can't be reached.

    Each run indexes a ticker's filings and queries them straight away, so an
    in-memory collection is a complete substitute within one process — it just
    isn't shared or persisted. That keeps retrieval working when a Qdrant Cloud
    cluster is suspended or no local server is running.
    """
    if settings.QDRANT_URL:
        try:
            client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY or None,
                timeout=settings.REQUEST_TIMEOUT,
                check_compatibility=False,
            )
            client.get_collections()
            return client
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Qdrant at QDRANT_URL is unreachable (%s); using an in-memory store.", exc
            )
    return QdrantClient(":memory:")


def backend_kind() -> str:
    """``"remote"`` or ``"in-memory"`` — which store ``get_client`` resolved to."""
    return "in-memory" if type(get_client()._client).__name__ == "QdrantLocal" else "remote"


def ensure_collection(client: QdrantClient | None = None) -> None:
    """Create the `sec_filings` collection (cosine, EMBEDDING_DIM) if absent."""
    client = client or get_client()
    if not client.collection_exists(COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIM, distance=Distance.COSINE
            ),
        )
        logger.info("Created Qdrant collection '%s'", COLLECTION)
    if backend_kind() == "in-memory":
        return  # the in-process store filters without payload indexes
    # Filtering needs keyword indexes on Qdrant Cloud; creating one is idempotent.
    for field in ("ticker", "section", "fingerprint"):
        try:
            client.create_payload_index(
                collection_name=COLLECTION,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Payload index on '%s' not created: %s", field, exc)


def _filter(ticker: str, section: str | None = None) -> Filter:
    must = [FieldCondition(key="ticker", match=MatchValue(value=ticker.upper()))]
    if section:
        must.append(FieldCondition(key="section", match=MatchValue(value=section)))
    return Filter(must=must)


def index_sections(
    ticker: str,
    sections: dict[str, str],
    metadata: dict[str, dict[str, Any]] | None = None,
) -> int:
    """Chunk, embed, and upsert filing sections for ``ticker``.

    ``sections`` maps a section name (``mda`` / ``risk_factors`` / ``business``)
    to its text; ``metadata`` optionally maps the same names to payload fields
    (form, filing date, source URL). Existing chunks for the ticker are deleted
    first so re-runs stay idempotent. Returns the number of chunks indexed
    (0 on failure or empty input).
    """
    ticker = ticker.upper()
    items: list[tuple[str, int, str]] = [
        (name, idx, chunk)
        for name, text in sections.items()
        for idx, chunk in enumerate(chunk_text(text))
    ]
    if not items:
        return 0
    # Identifies this exact set of chunks, so an unchanged filing isn't embedded twice.
    fingerprint = hashlib.sha1("\x00".join(chunk for _, _, chunk in items).encode()).hexdigest()

    try:
        client = get_client()
        ensure_collection(client)
        already = client.count(
            collection_name=COLLECTION,
            count_filter=Filter(
                must=[
                    *_filter(ticker).must,
                    FieldCondition(key="fingerprint", match=MatchValue(value=fingerprint)),
                ]
            ),
            exact=True,
        ).count
        if already == len(items):
            logger.info("Filing chunks for %s already indexed; skipping embedding", ticker)
            return already

        client.delete(
            collection_name=COLLECTION,
            points_selector=FilterSelector(filter=_filter(ticker)),
        )

        vectors = embed_texts([chunk for _, _, chunk in items])
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "ticker": ticker,
                    **((metadata or {}).get(name) or {}),
                    "section": name,
                    "fingerprint": fingerprint,
                    "chunk_index": idx,
                    "text": chunk,
                },
            )
            for (name, idx, chunk), vector in zip(items, vectors)
        ]
        for i in range(0, len(points), _UPSERT_BATCH):
            client.upsert(collection_name=COLLECTION, points=points[i : i + _UPSERT_BATCH])
        logger.info("Indexed %d filing chunks for %s", len(points), ticker)
        return len(points)
    except Exception as exc:  # noqa: BLE001 - RAG is best-effort
        logger.warning("Failed to index filing sections for %s: %s", ticker, exc)
        return 0


def query_filings(
    ticker: str, query_text: str, top_k: int = 5, section: str | None = None
) -> list[dict[str, Any]]:
    """Semantic search over a ticker's indexed filing chunks, optionally
    restricted to one section.

    Returns a list of ``{text, score, section, chunk_index, ...}`` dicts, or an
    empty list if nothing is indexed or the backend is unavailable.
    """
    try:
        client = get_client()
        if not client.collection_exists(COLLECTION):
            return []
        qvec = embed_query(query_text)
        response = client.query_points(
            collection_name=COLLECTION,
            query=qvec,
            query_filter=_filter(ticker, section),
            limit=top_k,
            with_payload=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Qdrant query failed for %s: %s", ticker, exc)
        return []

    results: list[dict[str, Any]] = []
    for point in response.points:
        payload = point.payload or {}
        results.append(
            {
                "text": payload.get("text", ""),
                "score": point.score,
                "section": payload.get("section"),
                "chunk_index": payload.get("chunk_index"),
                "form": payload.get("form"),
                "filing_date": payload.get("filing_date"),
            }
        )
    return results
