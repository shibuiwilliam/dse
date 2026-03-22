from __future__ import annotations

# Phase 1 + Phase 2 tools
from dse.agents.mma.tools.confidence import update_confidence_tool
from dse.agents.mma.tools.contradiction import detect_contradiction_tool, resolve_contradiction_tool

# Phase 3 tools
from dse.agents.mma.tools.importance import estimate_importance_tool, reinforce_memory_tool
from dse.agents.mma.tools.p3_compression import compress_memories_tool
from dse.agents.mma.tools.provenance import record_provenance_tool
from dse.agents.mma.tools.relation import classify_relation_tool, create_relation_tool
from dse.agents.mma.tools.store import store_memory_tool

__all__ = [
    "store_memory_tool",
    "detect_contradiction_tool",
    "resolve_contradiction_tool",
    "classify_relation_tool",
    "create_relation_tool",
    "update_confidence_tool",
    "record_provenance_tool",
    "estimate_importance_tool",
    "reinforce_memory_tool",
    "compress_memories_tool",
]
