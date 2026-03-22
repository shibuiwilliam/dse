// DSE Neo4j Schema Initialization — Phase 2 Complete
// Run with: make db-init

// ── Constraints ──────────────────────────────────────────────────────
CREATE CONSTRAINT memory_id_unique IF NOT EXISTS
  FOR (m:Memory) REQUIRE m.id IS UNIQUE;

CREATE CONSTRAINT conflict_id_unique IF NOT EXISTS
  FOR (c:ConflictRecord) REQUIRE c.id IS UNIQUE;

// ── Indexes ──────────────────────────────────────────────────────────
CREATE INDEX memory_namespace IF NOT EXISTS
  FOR (m:Memory) ON (m.namespace);

CREATE INDEX memory_type_idx IF NOT EXISTS
  FOR (m:Memory) ON (m.memory_type);

CREATE INDEX memory_created_at IF NOT EXISTS
  FOR (m:Memory) ON (m.created_at);

CREATE INDEX memory_confidence IF NOT EXISTS
  FOR (m:Memory) ON (m.confidence);

CREATE INDEX memory_is_archived IF NOT EXISTS
  FOR (m:Memory) ON (m.is_archived);

CREATE INDEX memory_verification_status IF NOT EXISTS
  FOR (m:Memory) ON (m.verification_status);

// ── Fulltext Index (requires APOC) ───────────────────────────────────
// Enables fast text search across Memory summaries
// Note: If APOC is not installed, this will fail silently
CALL db.index.fulltext.createNodeIndex(
  "memoryFulltext",
  ["Memory"],
  ["summary"],
  {analyzer: "standard"}
);

// ── Relationship Types (documentation only) ──────────────────────────
// SUPERSEDED_BY, COMPLEMENTS, CONTRADICTS, DERIVES, CAUSES,
// REFERENCES, HAS_CHILD, TEMPORALLY_PRECEDES
