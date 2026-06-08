"""Qdrant vector store for the `sec_filings` collection.

Indexes MD&A chunks (per ticker) and supports filtered semantic queries used by
the Analyst node. All operations degrade gracefully: if Qdrant or OpenAI is
unreachable, indexing returns 0 and queries return an empty list so the agent
pipeline keeps running.
"""
from __future__ import annotations

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
    PointStruct,
    VectorParams,
)

from backend.config import settings
from backend.rag.chunking import chunk_text
from backend.rag.embeddings import embed_query, embed_texts

logger = logging.getLogger(__name__)

COLLECTION = settings.QDRANT_COLLECTION


@lru_cache
def get_client() -> QdrantClient:
    return QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
        timeout=settings.REQUEST_TIMEOUT,
    )


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


def _ticker_filter(ticker: str) -> Filter:
    return Filter(
        must=[FieldCondition(key="ticker", match=MatchValue(value=ticker.upper()))]
    )


def index_mda(ticker: str, mda_text: str, metadata: dict[str, Any] | None = None) -> int:
    """Chunk, embed, and upsert MD&A text for ``ticker``.

    Existing chunks for the ticker are deleted first so re-runs stay idempotent.
    Returns the number of chunks indexed (0 on failure or empty input).
    """
    ticker = ticker.upper()
    chunks = chunk_text(mda_text)
    if not chunks:
        return 0

    try:
        client = get_client()
        ensure_collection(client)
        client.delete(
            collection_name=COLLECTION,
            points_selector=FilterSelector(filter=_ticker_filter(ticker)),
        )

        vectors = embed_texts(chunks)
        base_payload = {"ticker": ticker, **(metadata or {})}
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={**base_payload, "chunk_index": idx, "text": chunk},
            )
            for idx, (chunk, vector) in enumerate(zip(chunks, vectors))
        ]
        client.upsert(collection_name=COLLECTION, points=points)
        logger.info("Indexed %d MD&A chunks for %s", len(points), ticker)
        return len(points)
    except Exception as exc:  # noqa: BLE001 - RAG is best-effort
        logger.warning("Failed to index MD&A for %s: %s", ticker, exc)
        return 0


def query_filings(ticker: str, query_text: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Semantic search over a ticker's indexed MD&A chunks.

    Returns a list of ``{text, score, chunk_index, ...}`` dicts, or an empty list
    if nothing is indexed or the backend is unavailable.
    """
    try:
        client = get_client()
        if not client.collection_exists(COLLECTION):
            return []
        qvec = embed_query(query_text)
        response = client.query_points(
            collection_name=COLLECTION,
            query=qvec,
            query_filter=_ticker_filter(ticker),
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
                "chunk_index": payload.get("chunk_index"),
                "form": payload.get("form"),
                "filing_date": payload.get("filing_date"),
            }
        )
    return results
