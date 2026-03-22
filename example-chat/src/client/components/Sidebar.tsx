import React from "react";
import type { MemoryStatus, ToolActivity } from "../types.js";

interface Props {
  toolActivity: ToolActivity[];
  memoryStatus: MemoryStatus | null;
  sessionId: string;
  turnCount: number;
  scale?: number;
}

const TOOL_LABELS: Record<string, string> = {
  mcp__dse__retrieve_memories: "Recalling memories",
  mcp__dse__search_memories: "Text search",
  mcp__dse__store_memory: "Storing memory",
  mcp__dse__get_memory: "Reading memory",
  mcp__dse__update_memory: "Updating memory",
  mcp__dse__delete_memory: "Deleting memory",
  mcp__dse__list_namespaces: "Listing namespaces",
  mcp__dse__get_namespace: "Namespace stats",
  mcp__dse__create_namespace: "Creating namespace",
  mcp__dse__delete_namespace: "Deleting namespace",
  mcp__dse__get_related_memories: "Graph traversal",
  mcp__dse__create_memory_relation: "Creating relation",
  mcp__dse__working_memory_add: "Session write",
  mcp__dse__working_memory_get: "Session read",
};

const TOOL_GROUPS = [
  {
    label: "Retrieval",
    tools: [
      ["retrieve_memories", "Cascade search (BM25 + kNN + graph)"],
      ["search_memories", "Direct Elasticsearch text search"],
      ["get_memory", "Fetch by ID"],
      ["get_related_memories", "Graph neighbor traversal"],
    ],
  },
  {
    label: "Storage",
    tools: [
      ["store_memory", "Create with embedding + graph"],
      ["update_memory", "Partial field update"],
      ["delete_memory", "Remove from all stores"],
    ],
  },
  {
    label: "Graph",
    tools: [["create_memory_relation", "Create typed edge"]],
  },
  {
    label: "Namespaces",
    tools: [
      ["list_namespaces", "All available namespaces"],
      ["get_namespace", "Namespace stats"],
    ],
  },
  {
    label: "Session",
    tools: [
      ["working_memory_add", "Write to Redis Stream"],
      ["working_memory_get", "Read recent turns"],
    ],
  },
];

export function Sidebar({ toolActivity, memoryStatus, sessionId, turnCount, scale = 1 }: Props) {
  const s = (base: number) => Math.round(base * scale);

  return (
    <aside style={styles.sidebar}>
      <div style={styles.logo}>
        <span style={{ ...styles.logoIcon, fontSize: s(24) }}>{"🧠"}</span>
        <span style={{ ...styles.logoText, fontSize: s(18) }}>DSE Chat</span>
      </div>

      {/* Session info */}
      <div style={styles.section}>
        <h3 style={{ ...styles.sectionTitle, fontSize: s(12) }}>Session</h3>
        <div style={{ ...styles.stat, fontSize: s(14) }}>
          <span style={styles.statLabel}>ID</span>
          <span style={{ ...styles.statValue, fontSize: s(12) }}>{sessionId.slice(0, 20)}...</span>
        </div>
        <div style={{ ...styles.stat, fontSize: s(14) }}>
          <span style={styles.statLabel}>Turns</span>
          <span style={{ ...styles.statValue, fontSize: s(12) }}>{turnCount}</span>
        </div>
      </div>

      {/* Memory status */}
      {memoryStatus && (
        <div style={styles.section}>
          <h3 style={{ ...styles.sectionTitle, fontSize: s(12) }}>Last Turn</h3>
          <div style={{ ...styles.memoryStatus, fontSize: s(14) }}>
            <span style={{ ...(memoryStatus.stored_by_claude ? styles.statusOk : styles.statusWarn), fontSize: s(14) }}>
              {memoryStatus.stored_by_claude ? "✓" : "○"}
            </span>
            <span style={styles.statusText}>
              {memoryStatus.stored_by_claude ? "Claude stored" : "Claude skipped"}
            </span>
          </div>
          {memoryStatus.fallback_triggered && (
            <div style={{ ...styles.memoryStatus, fontSize: s(14) }}>
              <span style={{ ...styles.statusOk, fontSize: s(14) }}>✓</span>
              <span style={styles.statusText}>Fallback stored</span>
            </div>
          )}
        </div>
      )}

      {/* Tool activity */}
      {toolActivity.length > 0 && (
        <div style={styles.section}>
          <h3 style={{ ...styles.sectionTitle, fontSize: s(12) }}>Activity</h3>
          <ul style={styles.activityList}>
            {toolActivity.map((t, i) => (
              <li key={i} style={{ ...styles.activityItem, fontSize: s(14) }}>
                <span style={t.status === "done" ? { ...styles.dotDone, fontSize: s(14) } : { ...styles.dotRunning, fontSize: s(13) }}>
                  {t.status === "done" ? "✓" : "●"}
                </span>
                <span style={styles.activityText}>
                  {TOOL_LABELS[t.tool] ?? t.tool.replace("mcp__dse__", "")}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Available tools */}
      <div style={{ ...styles.section, flex: 1, overflowY: "auto" as const }}>
        <h3 style={{ ...styles.sectionTitle, fontSize: s(12) }}>
          DSE Tools ({TOOL_GROUPS.reduce((a, g) => a + g.tools.length, 0)})
        </h3>
        {TOOL_GROUPS.map((group) => (
          <div key={group.label} style={{ marginBottom: 10 }}>
            <span style={{ fontSize: s(11), fontWeight: 600, color: "#6b7280", textTransform: "uppercase" as const }}>
              {group.label}
            </span>
            <ul style={styles.toolList}>
              {group.tools.map(([name, desc]) => (
                <li key={name} style={styles.toolItem}>
                  <span style={{ ...styles.toolName, fontSize: s(13) }}>{name}</span>
                  <span style={{ ...styles.toolDesc, fontSize: s(12) }}>{desc}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div style={styles.footer}>
        <p style={{ ...styles.footerText, fontSize: s(12) }}>
          Powered by Claude Agent SDK + DSE
          <br />
          <span style={{ fontSize: s(11) }}>Elasticsearch · Neo4j · Redis · Temporal</span>
        </p>
      </div>
    </aside>
  );
}

const styles: Record<string, React.CSSProperties> = {
  sidebar: {
    width: 320,
    backgroundColor: "#1e1b2e",
    color: "#e5e7eb",
    display: "flex",
    flexDirection: "column",
    borderRight: "1px solid #374151",
    flexShrink: 0,
  },
  logo: {
    padding: "16px",
    display: "flex",
    alignItems: "center",
    gap: 10,
    borderBottom: "1px solid #374151",
  },
  logoIcon: { fontSize: 24 },
  logoText: { fontSize: 18, fontWeight: 700, color: "#c4b5fd" },
  section: { padding: "12px 16px" },
  sectionTitle: {
    fontSize: 12,
    fontWeight: 600,
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
    color: "#9ca3af",
    marginBottom: 8,
  },
  stat: {
    display: "flex",
    justifyContent: "space-between",
    padding: "3px 0",
    fontSize: 14,
  },
  statLabel: { color: "#6b7280" },
  statValue: { color: "#d1d5db", fontFamily: "monospace", fontSize: 12 },
  memoryStatus: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "3px 0",
    fontSize: 14,
  },
  statusOk: { color: "#34d399", fontSize: 14, fontWeight: 700 },
  statusWarn: { color: "#fbbf24", fontSize: 14 },
  statusText: { color: "#d1d5db" },
  toolList: { listStyle: "none", marginTop: 4 },
  toolItem: {
    padding: "3px 0",
    display: "flex",
    flexDirection: "column" as const,
  },
  toolName: {
    fontSize: 13,
    fontWeight: 500,
    color: "#a78bfa",
    fontFamily: "monospace",
  },
  toolDesc: { fontSize: 12, color: "#6b7280" },
  activityList: { listStyle: "none" },
  activityItem: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "3px 0",
    fontSize: 14,
  },
  activityText: { color: "#d1d5db" },
  dotRunning: { color: "#fbbf24", fontSize: 13 },
  dotDone: { color: "#34d399", fontSize: 14 },
  footer: {
    padding: "14px 16px",
    borderTop: "1px solid #374151",
  },
  footerText: {
    fontSize: 12,
    color: "#6b7280",
    textAlign: "center" as const,
    lineHeight: 1.5,
  },
};
