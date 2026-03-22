from __future__ import annotations

from functools import lru_cache

from dse.config import settings
from dse.pipeline.retrieval import CascadeRetrieval
from dse.services.cache import MockWorkingMemoryService, WorkingMemoryService
from dse.services.embedding import EmbeddingService, MockEmbeddingService
from dse.services.graph import GraphService, MockGraphService
from dse.services.llm import LLMService, MockLLMService
from dse.services.search import MockSearchService, SearchService
from dse.services.storage import MockStorageService, StorageService


def _use_mock_llm() -> bool:
    return settings.use_mock_llm


def _use_mock_infra() -> bool:
    return settings.use_mock_search


@lru_cache
def get_llm_service() -> LLMService:
    if _use_mock_llm():
        return MockLLMService()
    return LLMService()


@lru_cache
def get_embedding_service() -> EmbeddingService:
    if _use_mock_llm():
        return MockEmbeddingService()
    return EmbeddingService()


@lru_cache
def get_search_service() -> SearchService:
    if _use_mock_infra():
        return MockSearchService()
    return SearchService()


@lru_cache
def get_storage_service() -> StorageService:
    if _use_mock_infra():
        return MockStorageService()
    return StorageService()


@lru_cache
def get_graph_service() -> GraphService:
    if _use_mock_infra():
        return MockGraphService()
    return GraphService()


@lru_cache
def get_cache_service() -> WorkingMemoryService:
    if _use_mock_infra():
        return MockWorkingMemoryService()
    return WorkingMemoryService()


@lru_cache
def get_retrieval_pipeline() -> CascadeRetrieval:
    return CascadeRetrieval(
        search=get_search_service(),
        embedding=get_embedding_service(),
        graph=get_graph_service(),
        cache=get_cache_service(),
        storage=get_storage_service(),
        llm=get_llm_service(),
    )
