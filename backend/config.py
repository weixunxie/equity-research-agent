"""Central configuration loaded from environment variables (.env)."""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings sourced from environment variables."""

    # --- Secrets / endpoints ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")

    # --- Models ---
    CHAT_MODEL: str = os.getenv("CHAT_MODEL", "gpt-4o")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    # text-embedding-3-small -> 1536 dimensions. Update if you change the model.
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1536"))

    # --- RAG ---
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "sec_filings")
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))

    # --- SEC EDGAR ---
    # SEC's fair-access policy requires a User-Agent in "Name email@domain" form;
    # other formats (e.g. parenthetical, or browser-like) get a 403 from SEC's WAF.
    SEC_USER_AGENT: str = os.getenv(
        "SEC_USER_AGENT", "equity-research-agent research@example.com"
    )
    SEC_FTS_URL: str = "https://efts.sec.gov/LATEST/search-index"
    SEC_SUBMISSIONS_URL: str = "https://data.sec.gov/submissions/CIK{cik}.json"
    SEC_ARCHIVES_BASE: str = "https://www.sec.gov/Archives"

    # --- Misc ---
    NEWS_LOOKBACK_DAYS: int = int(os.getenv("NEWS_LOOKBACK_DAYS", "30"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))

    def validate(self) -> list[str]:
        """Return a list of human-readable problems with the current config."""
        problems: list[str] = []
        if not self.OPENAI_API_KEY:
            problems.append("OPENAI_API_KEY is not set (required for LLM + embeddings).")
        if not self.TAVILY_API_KEY:
            problems.append("TAVILY_API_KEY is not set (news retrieval will be skipped).")
        if not self.QDRANT_URL:
            problems.append("QDRANT_URL is not set (RAG retrieval will be skipped).")
        return problems


@lru_cache
def get_settings() -> Settings:
    """Cached singleton accessor for settings."""
    return Settings()


settings = get_settings()
