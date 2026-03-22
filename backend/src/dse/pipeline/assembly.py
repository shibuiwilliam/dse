from __future__ import annotations

import structlog

from dse.core.models import AssembledContext, ContextItem, SearchResult
from dse.services.storage import StorageService

logger = structlog.get_logger(__name__)

# Approximate tokens per character (for Japanese + mixed content)
CHARS_PER_TOKEN = 2


def estimate_tokens(text: str) -> int:
    """Rough token estimate. Japanese text is ~2 chars per token."""
    return max(1, len(text) // CHARS_PER_TOKEN)


class ContextAssembler:
    """Assembles search results into a token-budget-aware context package."""

    def __init__(self, storage: StorageService) -> None:
        self._storage = storage

    async def assemble(
        self,
        results: list[SearchResult],
        token_budget: int,
        *,
        query: str = "",
        namespace: str = "",
    ) -> AssembledContext:
        """Select and format results within the token budget.

        Uses tiered content selection:
          - Tier 3 (full): score > 0.8 and budget >= 500 tokens
          - Tier 2 (summary): budget >= 100 tokens
          - Tier 1 (reference): budget >= 20 tokens
        """
        items: list[ContextItem] = []
        used_tokens = 0

        for result in results:
            record = result.record
            remaining = token_budget - used_tokens

            if remaining < 20:
                break

            content: str
            tier: str

            if remaining >= 500 and result.score > 0.8 and record.content_path:
                # Tier 3: Full content
                try:
                    content = await self._storage.fetch_content(record.content_path)
                    tier = "full"
                except Exception:
                    content = record.summary
                    tier = "summary"
            elif remaining >= 100 and record.summary:
                # Tier 2: Summary
                content = record.summary
                tier = "summary"
            elif remaining >= 20:
                # Tier 1: Reference only
                content = f"[{record.memory_type.value}] {record.id}: {record.summary[:80]}..."
                tier = "reference"
            else:
                break

            tokens = estimate_tokens(content)
            if used_tokens + tokens > token_budget:
                # Truncate content to fit
                max_chars = (token_budget - used_tokens) * CHARS_PER_TOKEN
                content = content[:max_chars]
                tokens = estimate_tokens(content)
                tier = "truncated"

            items.append(
                ContextItem(
                    memory_id=record.id,
                    memory_type=record.memory_type,
                    content=content,
                    tier=tier,
                    score=result.score,
                    confidence=record.confidence,
                    created_at=record.created_at,
                    tokens=tokens,
                )
            )
            used_tokens += tokens

        logger.info(
            "assembly.complete",
            items=len(items),
            total_tokens=used_tokens,
            budget=token_budget,
        )

        return AssembledContext(
            items=items,
            total_tokens=used_tokens,
            query=query,
            namespace=namespace,
        )
