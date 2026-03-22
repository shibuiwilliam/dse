from __future__ import annotations

import structlog
from google import genai

from dse.config import settings
from dse.core.exceptions import EmbeddingError

logger = structlog.get_logger(__name__)

EMBEDDING_DIMS = 3072


class EmbeddingService:
    """Gemini Embedding client for vectorizing memory content."""

    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_embedding_model

    async def encode(self, text: str) -> list[float]:
        """Encode text for document storage (RETRIEVAL_DOCUMENT task type)."""
        try:
            result = await self._client.aio.models.embed_content(
                model=self._model,
                contents=text,
                config=genai.types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                ),
            )
            return list(result.embeddings[0].values)
        except Exception as e:
            logger.error("embedding.encode_failed", error=str(e), text_length=len(text))
            raise EmbeddingError(f"Failed to encode text: {e}") from e

    async def encode_query(self, text: str) -> list[float]:
        """Encode text for search query (RETRIEVAL_QUERY task type)."""
        try:
            result = await self._client.aio.models.embed_content(
                model=self._model,
                contents=text,
                config=genai.types.EmbedContentConfig(
                    task_type="RETRIEVAL_QUERY",
                ),
            )
            return list(result.embeddings[0].values)
        except Exception as e:
            logger.error("embedding.query_encode_failed", error=str(e))
            raise EmbeddingError(f"Failed to encode query: {e}") from e

    async def compute_similarity(self, vec_a: list[float], vec_b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(vec_a) != len(vec_b):
            raise EmbeddingError(f"Vector dimension mismatch: {len(vec_a)} vs {len(vec_b)}")
        dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=True))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


class MockEmbeddingService(EmbeddingService):
    """Mock embedding service for local development and testing."""

    def __init__(self) -> None:
        self._model = "mock-embedding"

    async def encode(self, text: str) -> list[float]:
        import hashlib

        # Generate deterministic vector with exact EMBEDDING_DIMS dimensions
        vector: list[float] = []
        seed = text.encode()
        i = 0
        while len(vector) < EMBEDDING_DIMS:
            h = hashlib.sha256(seed + i.to_bytes(4, "big")).digest()
            vector.extend(float(b) / 255.0 for b in h)
            i += 1
        return vector[:EMBEDDING_DIMS]

    async def encode_query(self, text: str) -> list[float]:
        return await self.encode(text)
