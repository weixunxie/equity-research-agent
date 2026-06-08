"""OpenAI embeddings (text-embedding-3-small) with simple batching."""
from __future__ import annotations

import logging
from functools import lru_cache

from openai import OpenAI

from backend.config import settings

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100  # inputs per embeddings request


@lru_cache
def _client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings, batching requests. Returns one vector per input."""
    if not texts:
        return []
    vectors: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        resp = _client().embeddings.create(model=settings.EMBEDDING_MODEL, input=batch)
        # API preserves input order in resp.data, but sort by index to be safe.
        for item in sorted(resp.data, key=lambda d: d.index):
            vectors.append(item.embedding)
    return vectors


def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    return embed_texts([text])[0]
