from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dse.api.routers import (
    conflicts,
    curation,
    graph,
    health,
    ingest,
    mcp_info,
    memories,
    namespaces,
    provenance,
    retrieve,
    working_memory,
)
from dse.config import configure_logging, settings
from dse.core.exceptions import DSEError

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Startup and shutdown lifecycle."""
    configure_logging(settings.log_level)
    logger.info(
        "app.starting",
        env=settings.app_env,
        mock_llm=settings.use_mock_llm,
        mock_search=settings.use_mock_search,
    )
    yield
    # Shutdown: close service connections
    import contextlib

    from dse.api.deps import get_cache_service, get_graph_service, get_search_service

    with contextlib.suppress(Exception):
        await get_search_service().close()
    with contextlib.suppress(Exception):
        await get_graph_service().close()
    with contextlib.suppress(Exception):
        await get_cache_service().close()
    logger.info("app.shutting_down")


app = FastAPI(
    title="DSE — Dynamic Search Engine for Agentic Memory",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)
app.include_router(memories.router)
app.include_router(retrieve.router)
app.include_router(graph.router)
app.include_router(conflicts.router)
app.include_router(working_memory.router)
app.include_router(provenance.router)
app.include_router(curation.router)
app.include_router(namespaces.router)
app.include_router(mcp_info.router)
app.include_router(ingest.router)


@app.exception_handler(DSEError)
async def dse_error_handler(request: Request, exc: DSEError) -> JSONResponse:
    """Handle all DSE domain exceptions with a standard error format."""
    status_map: dict[str, int] = {
        "MEMORY_NOT_FOUND": 404,
        "ACCESS_DENIED": 403,
        "CONFLICT_ERROR": 409,
        "PII_DETECTED": 422,
    }
    status_code = status_map.get(exc.code, 500)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": {},
            }
        },
    )
