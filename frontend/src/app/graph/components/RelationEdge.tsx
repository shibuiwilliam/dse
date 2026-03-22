"use client";

import {
  BaseEdge,
  EdgeLabelRenderer,
  getStraightPath,
  type EdgeProps,
} from "@xyflow/react";

const EDGE_COLORS: Record<string, string> = {
  SUPERSEDED_BY: "#f59e0b",
  COMPLEMENTS: "#10b981",
  CONTRADICTS: "#ef4444",
  DERIVES: "#6366f1",
  CAUSES: "#8b5cf6",
  REFERENCES: "#64748b",
  HAS_CHILD: "#06b6d4",
  TEMPORALLY_PRECEDES: "#d1d5db",
};

export interface RelationEdgeData {
  relationType: string;
  strength: number;
}

export function RelationEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  data,
}: EdgeProps) {
  const d = data as unknown as RelationEdgeData;
  const color = EDGE_COLORS[d?.relationType] ?? "#94a3b8";
  const isContradiction = d?.relationType === "CONTRADICTS";

  const [edgePath, labelX, labelY] = getStraightPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
  });

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: color,
          strokeWidth: 2,
          strokeDasharray: isContradiction ? "6 3" : undefined,
        }}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: "absolute",
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            fontSize: 8,
            fontWeight: 600,
            color,
            background: "rgba(255,255,255,0.85)",
            padding: "1px 4px",
            borderRadius: 3,
            pointerEvents: "all",
          }}
          className="nodrag nopan"
        >
          {d?.relationType ?? ""}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
