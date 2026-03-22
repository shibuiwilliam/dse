"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";

const TYPE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  semantic: { bg: "#f3e8ff", border: "#c084fc", text: "#7c3aed" },
  episodic: { bg: "#dbeafe", border: "#60a5fa", text: "#2563eb" },
  procedural: { bg: "#d1fae5", border: "#34d399", text: "#059669" },
  prospective: { bg: "#fef3c7", border: "#fbbf24", text: "#d97706" },
};

export interface MemoryNodeData {
  memoryType: string;
  confidence: number;
  summary: string;
  id: string;
  selected?: boolean;
}

export function MemoryNode({ data }: NodeProps) {
  const d = data as unknown as MemoryNodeData;
  const colors = TYPE_COLORS[d.memoryType] ?? TYPE_COLORS.episodic;
  const isSelected = d.selected ?? false;

  return (
    <div
      style={{
        background: isSelected ? colors.border : colors.bg,
        border: `2px solid ${colors.border}`,
        borderRadius: 10,
        padding: "8px 12px",
        minWidth: 150,
        maxWidth: 200,
        fontSize: 11,
        cursor: "pointer",
        boxShadow: isSelected
          ? `0 0 0 3px ${colors.border}40, 0 4px 12px ${colors.border}30`
          : "none",
        transition: "all 0.15s ease",
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: colors.border }} />

      <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 4 }}>
        <span
          style={{
            background: isSelected ? "#fff" : colors.border,
            color: isSelected ? colors.border : "#fff",
            borderRadius: 4,
            padding: "1px 6px",
            fontSize: 9,
            fontWeight: 600,
            textTransform: "uppercase",
          }}
        >
          {d.memoryType}
        </span>
        <span style={{ color: isSelected ? "#fff" : "#94a3b8", fontSize: 9 }}>
          {(d.confidence * 100).toFixed(0)}%
        </span>
      </div>

      <p
        style={{
          color: isSelected ? "#fff" : colors.text,
          fontWeight: 500,
          lineHeight: 1.3,
          overflow: "hidden",
          textOverflow: "ellipsis",
          display: "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical",
        }}
      >
        {d.summary || d.id.slice(0, 12) + "..."}
      </p>

      <Handle type="source" position={Position.Bottom} style={{ background: colors.border }} />
    </div>
  );
}
