from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends

from dse.api.deps import get_cache_service, get_graph_service
from dse.services.cache import CacheService
from dse.services.graph import GraphService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Basic liveness check — always returns ok if the process is running."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness_check(
    graph: Annotated[GraphService, Depends(get_graph_service)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> dict[str, object]:
    """Readiness check — verifies downstream services are reachable."""
    checks: dict[str, str] = {}

    # Check Redis
    try:
        await cache.set("health:ping", "pong")
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # Check Neo4j
    try:
        driver = await graph._get_driver()
        await driver.verify_connectivity()
        checks["neo4j"] = "ok"
    except Exception as e:
        checks["neo4j"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ready" if all_ok else "degraded", "checks": checks}
