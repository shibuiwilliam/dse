// DSE Neo4j Schema Initialization
// Run with: make db-init

// Constraints
CREATE CONSTRAINT memory_id_unique IF NOT EXISTS
  FOR (m:Memory) REQUIRE m.id IS UNIQUE;

// Indexes
CREATE INDEX memory_namespace IF NOT EXISTS
  FOR (m:Memory) ON (m.namespace);

CREATE INDEX memory_type IF NOT EXISTS
  FOR (m:Memory) ON (m.memory_type);

CREATE INDEX memory_created_at IF NOT EXISTS
  FOR (m:Memory) ON (m.created_at);

// Relationship types used in DSE:
// SUPERSEDED_BY, COMPLEMENTS, CONTRADICTS, DERIVES, CAUSES, REFERENCES,
// HAS_CHILD, TEMPORALLY_PRECEDES
