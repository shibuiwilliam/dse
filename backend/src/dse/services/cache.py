from __future__ import annotations

import json
from typing import Any

import structlog
from redis.asyncio import Redis

from dse.config import settings

logger = structlog.get_logger(__name__)


class WorkingMemoryService:
    """Redis-backed Working Memory buffer and cache layer.

    Manages session-scoped volatile memory (Redis Streams for turns,
    SET/GET for context) and API caches (search, embedding).
    Design ref: PROJECT.md Section 5.1
    """

    def __init__(self) -> None:
        self._redis: Redis | None = None  # type: ignore[type-arg]
        self._ttl = settings.redis_working_memory_ttl_seconds
        self._cache_ttl = settings.redis_cache_ttl_seconds

    async def _get_redis(self) -> Redis:  # type: ignore[type-arg]
        if self._redis is None:
            self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    # ── Session context ──────────────────────────────────────────────

    async def set_context(self, session_id: str, context: dict[str, Any]) -> None:
        """Store a session's current context."""
        redis = await self._get_redis()
        key = f"working_memory:{session_id}:context"
        await redis.setex(key, self._ttl, json.dumps(context, ensure_ascii=False))

    async def get_context(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve a session's context."""
        redis = await self._get_redis()
        key = f"working_memory:{session_id}:context"
        raw = await redis.get(key)
        return json.loads(raw) if raw else None

    async def delete_context(self, session_id: str) -> None:
        """Delete session context on session end."""
        redis = await self._get_redis()
        await redis.delete(f"working_memory:{session_id}:context")

    # ── Conversation turns (Redis Streams) ───────────────────────────

    async def append_turn(self, session_id: str, turn: dict[str, Any]) -> str:
        """Append a conversation turn to the session's Redis Stream.

        Returns the Stream entry ID.
        """
        redis = await self._get_redis()
        key = f"working_memory:{session_id}:turns"
        entry_id: str = await redis.xadd(  # type: ignore[assignment]
            key,
            {"data": json.dumps(turn, ensure_ascii=False)},
            maxlen=200,
        )
        await redis.expire(key, self._ttl)
        return entry_id

    async def get_recent_turns(self, session_id: str, *, count: int = 20) -> list[dict[str, Any]]:
        """Get the most recent conversation turns."""
        redis = await self._get_redis()
        key = f"working_memory:{session_id}:turns"
        entries = await redis.xrevrange(key, count=count)  # type: ignore[arg-type]
        return [json.loads(e[1]["data"]) for e in entries]

    async def snapshot_for_persistence(self, session_id: str) -> dict[str, Any]:
        """Create a snapshot for MMA to decide what to persist to DSE."""
        context = await self.get_context(session_id)
        turns = await self.get_recent_turns(session_id, count=50)
        return {"session_id": session_id, "context": context, "turns": turns}

    async def delete_session(self, session_id: str) -> None:
        """Remove all data for a session."""
        redis = await self._get_redis()
        await redis.delete(
            f"working_memory:{session_id}:context",
            f"working_memory:{session_id}:turns",
        )

    # ── Search result cache ──────────────────────────────────────────

    async def cache_search_result(self, query_hash: str, result: Any) -> None:
        redis = await self._get_redis()
        key = f"cache:search:{query_hash}"
        await redis.setex(key, self._cache_ttl, json.dumps(result, ensure_ascii=False))

    async def get_cached_search_result(self, query_hash: str) -> Any | None:
        redis = await self._get_redis()
        key = f"cache:search:{query_hash}"
        raw = await redis.get(key)
        return json.loads(raw) if raw else None

    # ── Embedding cache ──────────────────────────────────────────────

    async def cache_embedding(self, text_hash: str, embedding: list[float]) -> None:
        """Cache a generated embedding to avoid redundant Gemini API calls."""
        redis = await self._get_redis()
        key = f"cache:embedding:{text_hash}"
        await redis.setex(key, 3600 * 24, json.dumps(embedding))

    async def get_cached_embedding(self, text_hash: str) -> list[float] | None:
        redis = await self._get_redis()
        key = f"cache:embedding:{text_hash}"
        raw = await redis.get(key)
        return json.loads(raw) if raw else None

    # ── Memory record cache (for backward compat) ─────────────────

    async def cache_memory(self, memory_id: str, data: dict[str, Any]) -> None:
        """Cache a memory record for fast retrieval."""
        redis = await self._get_redis()
        await redis.setex(f"cache:memory:{memory_id}", self._cache_ttl, json.dumps(data))

    async def get_cached_memory(self, memory_id: str) -> dict[str, Any] | None:
        redis = await self._get_redis()
        raw = await redis.get(f"cache:memory:{memory_id}")
        return json.loads(raw) if raw else None

    async def invalidate_memory(self, memory_id: str) -> None:
        """Remove a cached memory record."""
        redis = await self._get_redis()
        await redis.delete(f"cache:memory:{memory_id}")

    # ── Generic helpers ──────────────────────────────────────────────

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        redis = await self._get_redis()
        if ttl:
            await redis.setex(key, ttl, value)
        else:
            await redis.set(key, value)

    async def get(self, key: str) -> str | None:
        redis = await self._get_redis()
        return await redis.get(key)  # type: ignore[return-value]


class MockWorkingMemoryService(WorkingMemoryService):
    """In-memory mock for testing."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._streams: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        self._counter = 0

    async def close(self) -> None:
        pass

    async def set_context(self, session_id: str, context: dict[str, Any]) -> None:
        self._store[f"working_memory:{session_id}:context"] = json.dumps(context)

    async def get_context(self, session_id: str) -> dict[str, Any] | None:
        raw = self._store.get(f"working_memory:{session_id}:context")
        return json.loads(raw) if raw else None

    async def delete_context(self, session_id: str) -> None:
        self._store.pop(f"working_memory:{session_id}:context", None)

    async def append_turn(self, session_id: str, turn: dict[str, Any]) -> str:
        key = f"working_memory:{session_id}:turns"
        if key not in self._streams:
            self._streams[key] = []
        self._counter += 1
        entry_id = f"{self._counter}-0"
        self._streams[key].append((entry_id, turn))
        # Enforce maxlen 200
        if len(self._streams[key]) > 200:
            self._streams[key] = self._streams[key][-200:]
        return entry_id

    async def get_recent_turns(self, session_id: str, *, count: int = 20) -> list[dict[str, Any]]:
        key = f"working_memory:{session_id}:turns"
        entries = self._streams.get(key, [])
        return [e[1] for e in reversed(entries[-count:])]

    async def snapshot_for_persistence(self, session_id: str) -> dict[str, Any]:
        context = await self.get_context(session_id)
        turns = await self.get_recent_turns(session_id, count=50)
        return {"session_id": session_id, "context": context, "turns": turns}

    async def delete_session(self, session_id: str) -> None:
        self._store.pop(f"working_memory:{session_id}:context", None)
        self._streams.pop(f"working_memory:{session_id}:turns", None)

    async def cache_search_result(self, query_hash: str, result: Any) -> None:
        self._store[f"cache:search:{query_hash}"] = json.dumps(result)

    async def get_cached_search_result(self, query_hash: str) -> Any | None:
        raw = self._store.get(f"cache:search:{query_hash}")
        return json.loads(raw) if raw else None

    async def cache_embedding(self, text_hash: str, embedding: list[float]) -> None:
        self._store[f"cache:embedding:{text_hash}"] = json.dumps(embedding)

    async def get_cached_embedding(self, text_hash: str) -> list[float] | None:
        raw = self._store.get(f"cache:embedding:{text_hash}")
        return json.loads(raw) if raw else None

    async def cache_memory(self, memory_id: str, data: dict[str, Any]) -> None:
        self._store[f"cache:memory:{memory_id}"] = json.dumps(data)

    async def get_cached_memory(self, memory_id: str) -> dict[str, Any] | None:
        raw = self._store.get(f"cache:memory:{memory_id}")
        return json.loads(raw) if raw else None

    async def invalidate_memory(self, memory_id: str) -> None:
        self._store.pop(f"cache:memory:{memory_id}", None)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self._store[key] = value

    async def get(self, key: str) -> str | None:
        return self._store.get(key)


# Keep backwards-compat alias
CacheService = WorkingMemoryService
MockCacheService = MockWorkingMemoryService
