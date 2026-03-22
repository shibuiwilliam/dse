from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio

# Force mock mode for all tests
os.environ["USE_MOCK_LLM"] = "true"
os.environ["USE_MOCK_SEARCH"] = "true"
os.environ["APP_ENV"] = "local"
os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"
os.environ["GEMINI_API_KEY"] = "test-key"


@pytest.fixture
def namespace() -> str:
    return "agent:test/project:test"


@pytest_asyncio.fixture
async def mock_search_service() -> AsyncGenerator:
    from dse.services.search import MockSearchService

    service = MockSearchService()
    yield service


@pytest_asyncio.fixture
async def mock_storage_service() -> AsyncGenerator:
    from dse.services.storage import MockStorageService

    service = MockStorageService()
    yield service


@pytest_asyncio.fixture
async def mock_graph_service() -> AsyncGenerator:
    from dse.services.graph import MockGraphService

    service = MockGraphService()
    yield service


@pytest_asyncio.fixture
async def mock_cache_service() -> AsyncGenerator:
    from dse.services.cache import MockCacheService

    service = MockCacheService()
    yield service


@pytest_asyncio.fixture
async def mock_embedding_service() -> AsyncGenerator:
    from dse.services.embedding import MockEmbeddingService

    service = MockEmbeddingService()
    yield service


@pytest_asyncio.fixture
async def mock_llm_service() -> AsyncGenerator:
    from dse.services.llm import MockLLMService

    service = MockLLMService()
    yield service
