from __future__ import annotations

from typing import Any

import structlog
from elasticsearch import AsyncElasticsearch, NotFoundError

from dse.config import settings
from dse.core.exceptions import SearchServiceError
from dse.core.models import MemoryRecord

logger = structlog.get_logger(__name__)

# Elasticsearch index mapping for DSE memories
INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "namespace": {"type": "keyword"},
            "content_path": {"type": "keyword", "index": False},
            "summary": {"type": "text", "analyzer": "standard"},
            "content_text": {"type": "text", "analyzer": "standard"},
            "embedding": {
                "type": "dense_vector",
                "dims": settings.elasticsearch_vector_dims,
                "index": True,
                "similarity": "cosine",
            },
            "memory_type": {"type": "keyword"},
            "memory_subtype": {"type": "keyword"},
            "content_type": {"type": "keyword"},
            "confidence": {"type": "float"},
            "confidence_basis": {"type": "keyword"},
            "corroborating_sources": {"type": "integer"},
            "contradicting_sources": {"type": "integer"},
            "confidence_updated_at": {"type": "keyword"},
            "source_type": {"type": "keyword"},
            "source_id": {"type": "keyword"},
            "verification_status": {"type": "keyword"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
            "accessed_at": {"type": "date"},
            "expires_at": {"type": "date"},
            "access_count": {"type": "integer"},
            "access_count_7d": {"type": "integer"},
            "access_count_30d": {"type": "integer"},
            "last_access_utility": {"type": "float"},
            "decay_score": {"type": "float"},
            "importance_score": {"type": "float"},
            "superseded_by": {"type": "keyword"},
            "tags": {"type": "keyword"},
            "entities": {"type": "keyword"},
            "language": {"type": "keyword"},
            "trigger_type": {"type": "keyword"},
            "trigger_at": {"type": "date"},
            "trigger_condition": {"type": "keyword", "index": False},
            "is_triggered": {"type": "boolean"},
            "is_archived": {"type": "boolean"},
            "neighbor_ids": {"type": "keyword"},
        },
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
}


class SearchService:
    """Elasticsearch client for memory search and indexing.

    Supports full-text search (BM25), vector search (kNN), hybrid search,
    and filtered queries.
    """

    def __init__(self) -> None:
        self._client: AsyncElasticsearch | None = None
        self._index = settings.elasticsearch_index

    async def _get_client(self) -> AsyncElasticsearch:
        if self._client is None:
            self._client = AsyncElasticsearch(settings.elasticsearch_url)
            # Ensure index exists with correct mapping
            if not await self._client.indices.exists(index=self._index):
                await self._client.indices.create(index=self._index, body=INDEX_MAPPING)
                logger.info("search.index_created", index=self._index)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    # ── Search ───────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        *,
        memory_types: list[str] | None = None,
        namespace: str | None = None,
        top_k: int = 20,
        filter_archived: bool = True,
    ) -> list[dict[str, Any]]:
        """Execute a text search with optional filters.

        If query is empty, performs a match_all with filters.
        If query matches a UUID pattern, includes an ID term match.
        """
        try:
            client = await self._get_client()
            filters = self._build_filters(memory_types, namespace, filter_archived)

            if query:
                body: dict[str, Any] = {
                    "query": {
                        "bool": {
                            "should": [
                                {"term": {"id": {"value": query, "boost": 10.0}}},
                                {
                                    "multi_match": {
                                        "query": query,
                                        "fields": ["summary^3", "content_text"],
                                    }
                                },
                            ],
                            "filter": filters,
                            "minimum_should_match": 1,
                        },
                    },
                    "size": top_k,
                }
            else:
                body = {
                    "query": {"bool": {"filter": filters}} if filters else {"match_all": {}},
                    "size": top_k,
                }

            resp = await client.search(index=self._index, body=body)
            return [self._parse_hit(hit) for hit in resp["hits"]["hits"]]
        except Exception as e:
            logger.error("search.failed", error=str(e), query=query[:50] if query else "")
            raise SearchServiceError(f"Search failed: {e}") from e

    async def vector_search(
        self,
        embedding: list[float],
        *,
        namespace: str | None = None,
        memory_types: list[str] | None = None,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Execute a kNN vector search."""
        try:
            client = await self._get_client()
            filters = self._build_filters(memory_types, namespace, filter_archived=True)

            body: dict[str, Any] = {
                "knn": {
                    "field": "embedding",
                    "query_vector": embedding,
                    "k": top_k,
                    "num_candidates": top_k * 5,
                },
                "size": top_k,
            }
            if filters:
                body["knn"]["filter"] = {"bool": {"filter": filters}}

            resp = await client.search(index=self._index, body=body)
            results = [self._parse_hit(hit) for hit in resp["hits"]["hits"]]
            if min_score > 0:
                results = [r for r in results if r.get("_score", 0) >= min_score]
            return results
        except Exception as e:
            logger.error("search.vector_search_failed", error=str(e))
            raise SearchServiceError(f"Vector search failed: {e}") from e

    async def hybrid_search(
        self,
        query: str,
        embedding: list[float],
        *,
        namespace: str | None = None,
        memory_types: list[str] | None = None,
        top_k: int = 20,
        text_boost: float = 0.5,
        vector_boost: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Execute a hybrid search combining BM25 text + kNN vector."""
        try:
            client = await self._get_client()
            filters = self._build_filters(memory_types, namespace, filter_archived=True)

            body: dict[str, Any] = {
                "query": {
                    "bool": {
                        "should": [
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["summary^3", "content_text"],
                                    "boost": text_boost,
                                }
                            },
                        ],
                        "filter": filters,
                    },
                },
                "knn": {
                    "field": "embedding",
                    "query_vector": embedding,
                    "k": top_k,
                    "num_candidates": top_k * 5,
                    "boost": vector_boost,
                },
                "size": top_k,
            }

            resp = await client.search(index=self._index, body=body)
            return [self._parse_hit(hit) for hit in resp["hits"]["hits"]]
        except Exception as e:
            logger.error("search.hybrid_failed", error=str(e))
            raise SearchServiceError(f"Hybrid search failed: {e}") from e

    # ── CRUD ─────────────────────────────────────────────────────────

    async def upsert(self, record: MemoryRecord) -> str:
        """Index (create or update) a memory record."""
        try:
            client = await self._get_client()
            doc = record.model_dump(mode="json")
            # Remove summary_embedding to save space (we only index embedding)
            doc.pop("summary_embedding", None)
            await client.index(index=self._index, id=record.id, document=doc)
            logger.info("search.upserted", memory_id=record.id)
            return record.id
        except Exception as e:
            logger.error("search.upsert_failed", error=str(e), memory_id=record.id)
            raise SearchServiceError(f"Upsert failed for {record.id}: {e}") from e

    async def get_by_id(self, memory_id: str) -> dict[str, Any] | None:
        """Get a single document by ID. Returns None if not found."""
        try:
            client = await self._get_client()
            resp = await client.get(index=self._index, id=memory_id)
            return {**resp["_source"], "id": resp["_id"]}
        except NotFoundError:
            return None
        except Exception as e:
            logger.error("search.get_by_id_failed", error=str(e), memory_id=memory_id)
            return None

    async def patch(self, memory_id: str, fields: dict[str, Any]) -> None:
        """Partially update specific fields of a document."""
        try:
            client = await self._get_client()
            await client.update(index=self._index, id=memory_id, doc=fields)
            logger.info("search.patched", memory_id=memory_id, fields=list(fields.keys()))
        except Exception as e:
            logger.error("search.patch_failed", error=str(e), memory_id=memory_id)
            raise SearchServiceError(f"Patch failed for {memory_id}: {e}") from e

    async def delete(self, memory_id: str) -> None:
        """Delete a document by ID."""
        try:
            client = await self._get_client()
            await client.delete(index=self._index, id=memory_id, ignore=[404])
            logger.info("search.deleted", memory_id=memory_id)
        except Exception as e:
            logger.error("search.delete_failed", error=str(e), memory_id=memory_id)
            raise SearchServiceError(f"Delete failed for {memory_id}: {e}") from e

    # ── Namespace listing ────────────────────────────────────────────

    async def list_namespaces(self) -> list[str]:
        """Return all distinct namespace values in the index."""
        try:
            client = await self._get_client()
            body: dict[str, Any] = {
                "size": 0,
                "aggs": {
                    "namespaces": {
                        "terms": {"field": "namespace", "size": 500},
                    },
                },
            }
            resp = await client.search(index=self._index, body=body)
            buckets = resp.get("aggregations", {}).get("namespaces", {}).get("buckets", [])
            return [b["key"] for b in buckets]
        except Exception as e:
            logger.error("search.list_namespaces_failed", error=str(e))
            return []

    async def get_namespace_stats(self, namespace: str) -> dict[str, Any]:
        """Return stats for a single namespace (count, type distribution)."""
        try:
            client = await self._get_client()
            body: dict[str, Any] = {
                "size": 0,
                "track_total_hits": True,
                "query": {"term": {"namespace": namespace}},
                "aggs": {
                    "memory_types": {
                        "terms": {"field": "memory_type"},
                    },
                    "archived_count": {
                        "filter": {"term": {"is_archived": True}},
                    },
                },
            }
            resp = await client.search(index=self._index, body=body)
            total = resp["hits"]["total"]["value"]
            aggs = resp.get("aggregations", {})
            type_dist = {
                b["key"]: b["doc_count"] for b in aggs.get("memory_types", {}).get("buckets", [])
            }
            archived = aggs.get("archived_count", {}).get("doc_count", 0)
            return {
                "namespace": namespace,
                "total_memories": total,
                "archived_count": archived,
                "memory_type_distribution": type_dist,
            }
        except Exception as e:
            logger.error("search.get_namespace_stats_failed", error=str(e), namespace=namespace)
            raise SearchServiceError(f"Namespace stats failed: {e}") from e

    async def get_curation_stats(self, namespace: str) -> dict[str, Any]:
        """Return curation dashboard stats (type dist, decay dist, avg importance)."""
        try:
            client = await self._get_client()
            body: dict[str, Any] = {
                "size": 0,
                "track_total_hits": True,
                "query": {"term": {"namespace": namespace}},
                "aggs": {
                    "memory_types": {
                        "terms": {"field": "memory_type"},
                    },
                    "active": {
                        "filter": {"range": {"decay_score": {"gt": 0.4}}},
                    },
                    "warm": {
                        "filter": {"range": {"decay_score": {"gt": 0.2, "lte": 0.4}}},
                    },
                    "archive": {
                        "filter": {"range": {"decay_score": {"lte": 0.2}}},
                    },
                    "avg_importance": {
                        "avg": {"field": "importance_score"},
                    },
                },
            }
            resp = await client.search(index=self._index, body=body)
            total = resp["hits"]["total"]["value"]
            aggs = resp.get("aggregations", {})
            type_dist = {
                b["key"]: b["doc_count"]
                for b in aggs.get("memory_types", {}).get("buckets", [])
            }
            avg_imp = aggs.get("avg_importance", {}).get("value") or 0.0
            return {
                "namespace": namespace,
                "total_memories": total,
                "memory_type_distribution": type_dist,
                "decay_distribution": {
                    "active": aggs.get("active", {}).get("doc_count", 0),
                    "warm": aggs.get("warm", {}).get("doc_count", 0),
                    "archive": aggs.get("archive", {}).get("doc_count", 0),
                },
                "avg_importance": round(avg_imp, 3),
            }
        except Exception as e:
            logger.error("search.get_curation_stats_failed", error=str(e))
            raise SearchServiceError(f"Curation stats failed: {e}") from e

    async def get_namespace_detailed_stats(self, namespace: str) -> dict[str, Any]:
        """Return detailed stats including decay distribution via ES aggregations."""
        try:
            client = await self._get_client()
            body: dict[str, Any] = {
                "size": 0,
                "track_total_hits": True,
                "query": {"term": {"namespace": namespace}},
                "aggs": {
                    "memory_types": {
                        "terms": {"field": "memory_type"},
                    },
                    "active_count": {
                        "filter": {"range": {"decay_score": {"gt": 0.4}}},
                    },
                    "warm_count": {
                        "filter": {"range": {"decay_score": {"gt": 0.2, "lte": 0.4}}},
                    },
                    "archived_count": {
                        "filter": {"term": {"is_archived": True}},
                    },
                },
            }
            resp = await client.search(index=self._index, body=body)
            total = resp["hits"]["total"]["value"]
            aggs = resp.get("aggregations", {})
            type_dist = {
                b["key"]: b["doc_count"]
                for b in aggs.get("memory_types", {}).get("buckets", [])
            }
            return {
                "namespace": namespace,
                "total_memories": total,
                "active_count": aggs.get("active_count", {}).get("doc_count", 0),
                "warm_count": aggs.get("warm_count", {}).get("doc_count", 0),
                "archived_count": aggs.get("archived_count", {}).get("doc_count", 0),
                "memory_type_distribution": type_dist,
            }
        except Exception as e:
            logger.error("search.get_namespace_detailed_stats_failed", error=str(e))
            raise SearchServiceError(f"Detailed stats failed: {e}") from e

    async def delete_by_namespace(self, namespace: str) -> int:
        """Delete all documents in a namespace. Returns number of deleted docs."""
        try:
            client = await self._get_client()
            resp = await client.delete_by_query(
                index=self._index,
                body={"query": {"term": {"namespace": namespace}}},
            )
            deleted = resp.get("deleted", 0)
            logger.info("search.namespace_deleted", namespace=namespace, deleted=deleted)
            return deleted
        except Exception as e:
            logger.error("search.delete_by_namespace_failed", error=str(e), namespace=namespace)
            raise SearchServiceError(f"Delete namespace failed: {e}") from e

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _build_filters(
        memory_types: list[str] | None,
        namespace: str | None,
        filter_archived: bool,
    ) -> list[dict[str, Any]]:
        """Build Elasticsearch bool filter clauses."""
        filters: list[dict[str, Any]] = []
        if memory_types:
            filters.append({"terms": {"memory_type": memory_types}})
        if namespace:
            filters.append({"term": {"namespace": namespace}})
        if filter_archived:
            filters.append({"term": {"is_archived": False}})
        return filters

    @staticmethod
    def _parse_hit(hit: dict[str, Any]) -> dict[str, Any]:
        """Convert an ES hit to a flat dict with id."""
        source = hit.get("_source", {})
        source["id"] = hit["_id"]
        source["_score"] = hit.get("_score", 0)
        return source


# ---------------------------------------------------------------------------
# Mock for testing (unchanged interface)
# ---------------------------------------------------------------------------


class MockSearchService(SearchService):
    """In-memory mock for unit tests. No Elasticsearch dependency."""

    def __init__(self) -> None:
        self._records: dict[str, MemoryRecord] = {}

    async def close(self) -> None:
        pass

    async def search(
        self,
        query: str,
        *,
        memory_types: list[str] | None = None,
        namespace: str | None = None,
        top_k: int = 20,
        filter_archived: bool = True,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for record in self._records.values():
            if filter_archived and record.is_archived:
                continue
            if namespace and record.namespace != namespace:
                continue
            if memory_types and record.memory_type not in memory_types:
                continue
            if (
                query == record.id
                or query.lower() in record.content_text.lower()
                or query.lower() in record.summary.lower()
            ):
                results.append(record.to_index_dict())
        return results[:top_k]

    async def vector_search(
        self,
        embedding: list[float],
        *,
        namespace: str | None = None,
        memory_types: list[str] | None = None,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        return await self.search("", namespace=namespace, memory_types=memory_types, top_k=top_k)

    async def hybrid_search(
        self,
        query: str,
        embedding: list[float],
        *,
        namespace: str | None = None,
        memory_types: list[str] | None = None,
        top_k: int = 20,
        text_boost: float = 0.5,
        vector_boost: float = 0.5,
    ) -> list[dict[str, Any]]:
        return await self.search(query, namespace=namespace, memory_types=memory_types, top_k=top_k)

    async def upsert(self, record: MemoryRecord) -> str:
        self._records[record.id] = record
        return record.id

    async def get_by_id(self, memory_id: str) -> dict[str, Any] | None:
        record = self._records.get(memory_id)
        return record.to_index_dict() if record else None

    async def patch(self, memory_id: str, fields: dict[str, Any]) -> None:
        record = self._records.get(memory_id)
        if record:
            data = record.model_dump(mode="json")
            data.update(fields)
            self._records[memory_id] = MemoryRecord(**data)

    async def delete(self, memory_id: str) -> None:
        self._records.pop(memory_id, None)

    async def list_namespaces(self) -> list[str]:
        return sorted({r.namespace for r in self._records.values()})

    async def get_namespace_stats(self, namespace: str) -> dict[str, Any]:
        records = [r for r in self._records.values() if r.namespace == namespace]
        type_dist: dict[str, int] = {}
        archived = 0
        for r in records:
            mt = r.memory_type.value if hasattr(r.memory_type, "value") else str(r.memory_type)
            type_dist[mt] = type_dist.get(mt, 0) + 1
            if r.is_archived:
                archived += 1
        return {
            "namespace": namespace,
            "total_memories": len(records),
            "archived_count": archived,
            "memory_type_distribution": type_dist,
        }

    async def get_curation_stats(self, namespace: str) -> dict[str, Any]:
        records = [r for r in self._records.values() if r.namespace == namespace]
        type_dist: dict[str, int] = {}
        decay_buckets = {"active": 0, "warm": 0, "archive": 0}
        total_importance = 0.0
        for r in records:
            mt = r.memory_type.value if hasattr(r.memory_type, "value") else str(r.memory_type)
            type_dist[mt] = type_dist.get(mt, 0) + 1
            if r.decay_score > 0.4:
                decay_buckets["active"] += 1
            elif r.decay_score > 0.2:
                decay_buckets["warm"] += 1
            else:
                decay_buckets["archive"] += 1
            total_importance += r.importance_score
        return {
            "namespace": namespace,
            "total_memories": len(records),
            "memory_type_distribution": type_dist,
            "decay_distribution": decay_buckets,
            "avg_importance": round(total_importance / max(len(records), 1), 3),
        }

    async def get_namespace_detailed_stats(self, namespace: str) -> dict[str, Any]:
        records = [r for r in self._records.values() if r.namespace == namespace]
        type_dist: dict[str, int] = {}
        active = warm = archived = 0
        for r in records:
            mt = r.memory_type.value if hasattr(r.memory_type, "value") else str(r.memory_type)
            type_dist[mt] = type_dist.get(mt, 0) + 1
            if r.decay_score > 0.4:
                active += 1
            elif r.decay_score > 0.2:
                warm += 1
            if r.is_archived:
                archived += 1
        return {
            "namespace": namespace,
            "total_memories": len(records),
            "active_count": active,
            "warm_count": warm,
            "archived_count": archived,
            "memory_type_distribution": type_dist,
        }

    async def delete_by_namespace(self, namespace: str) -> int:
        to_delete = [mid for mid, r in self._records.items() if r.namespace == namespace]
        for mid in to_delete:
            del self._records[mid]
        return len(to_delete)
