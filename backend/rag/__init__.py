"""RAG layer: token chunking, OpenAI embeddings, and the Qdrant vector store."""
from backend.rag.chunking import chunk_text
from backend.rag.embeddings import embed_query, embed_texts
from backend.rag.qdrant_store import index_sections, query_filings

__all__ = ["chunk_text", "embed_texts", "embed_query", "index_sections", "query_filings"]
