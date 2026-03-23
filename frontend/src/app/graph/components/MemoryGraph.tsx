"use client";

import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge,
  type EdgeMouseHandler,
  type Node,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchSubgraph } from "@/lib/api/graph";
import { ALL_EDGE_TYPES, EdgeLegend } from "./EdgeLegend";
import { MemoryNode } from "./MemoryNode";
import { RelationEdge } from "./RelationEdge";

const nodeTypes = { memory: MemoryNode };
const edgeTypes = { relation: RelationEdge };

export interface SelectedEdge {
  id: string;
  source: string;
  target: string;
  relationType: string;
  strength: number | null;
}

interface Props {
  namespace: string;
  selectedNodeId: string | null;
  onNodeSelect: (nodeId: string | null) => void;
  onEdgeSelect: (edge: SelectedEdge | null) => void;
}

export function MemoryGraph({ namespace, selectedNodeId, onNodeSelect, onEdgeSelect }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ["graph", namespace],
    queryFn: () => fetchSubgraph(namespace, 200),
    refetchInterval: 30_000,
    enabled: !!namespace,
  });

  // Random pick — null means show all, string means show only that node's neighborhood
  const [pickedNodeId, setPickedNodeId] = useState<string | null>(null);

  // Edge type filter — all enabled by default
  const [enabledTypes, setEnabledTypes] = useState<Set<string>>(
    () => new Set(ALL_EDGE_TYPES.map((e) => e.type)),
  );

  const handleToggleType = useCallback((type: string) => {
    setEnabledTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }, []);

  // Edge counts from raw data (before filtering)
  const edgeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const e of data?.edges ?? []) {
      if (e.relation_type) {
        counts[e.relation_type] = (counts[e.relation_type] ?? 0) + 1;
      }
    }
    return counts;
  }, [data]);

  // Filter edges by enabled types, then find connected node IDs
  const { filteredEdges, connectedNodeIds } = useMemo(() => {
    let edges = (data?.edges ?? []).filter(
      (e) => e.source && e.target && e.relation_type && enabledTypes.has(e.relation_type),
    );

    // If a node is picked, only show edges touching that node
    if (pickedNodeId) {
      edges = edges.filter((e) => e.source === pickedNodeId || e.target === pickedNodeId);
    }

    const ids = new Set<string>();
    for (const e of edges) {
      ids.add(e.source);
      ids.add(e.target);
    }
    return { filteredEdges: edges, connectedNodeIds: ids };
  }, [data, enabledTypes, pickedNodeId]);

  // All node IDs that have at least one edge (for random pick pool)
  const allConnectedNodeIds = useMemo(() => {
    const ids = new Set<string>();
    for (const e of data?.edges ?? []) {
      if (e.source && e.target) {
        ids.add(e.source);
        ids.add(e.target);
      }
    }
    return ids;
  }, [data]);

  const handleRandomPick = useCallback(() => {
    const pool = Array.from(allConnectedNodeIds);
    if (pool.length === 0) return;
    const idx = Math.floor(Math.random() * pool.length);
    setPickedNodeId(pool[idx]);
    onNodeSelect(null);
    onEdgeSelect(null);
  }, [allConnectedNodeIds, onNodeSelect, onEdgeSelect]);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  useEffect(() => {
    if (!data) return;

    // Only show nodes that have at least one visible edge
    const visible = (data.nodes ?? []).filter((n) => connectedNodeIds.has(n.id));
    const count = visible.length;
    const radius = Math.max(250, count * 18);
    const cx = radius + 100;
    const cy = radius + 100;

    const rfNodes: Node[] = visible.map((n, i) => {
      const angle = (2 * Math.PI * i) / Math.max(count, 1);
      return {
        id: n.id,
        type: "memory",
        position: {
          x: cx + radius * Math.cos(angle),
          y: cy + radius * Math.sin(angle),
        },
        data: {
          memoryType: n.memory_type,
          confidence: n.confidence ?? 0.5,
          summary: "",
          id: n.id,
          selected: n.id === selectedNodeId,
        },
      };
    });

    const rfEdges: Edge[] = filteredEdges.map((e, i) => ({
      id: `${e.source}-${e.target}-${e.relation_type}-${i}`,
      source: e.source,
      target: e.target,
      type: "relation",
      data: {
        relationType: e.relation_type,
        strength: e.strength ?? 0.5,
      },
    }));

    setNodes(rfNodes);
    setEdges(rfEdges);
  }, [data, filteredEdges, connectedNodeIds, selectedNodeId, setNodes, setEdges]);

  // Update selected flag without re-layout
  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: { ...n.data, selected: n.id === selectedNodeId },
      })),
    );
  }, [selectedNodeId, setNodes]);

  const handleNodeClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      onEdgeSelect(null);
      onNodeSelect(node.id === selectedNodeId ? null : node.id);
    },
    [selectedNodeId, onNodeSelect, onEdgeSelect],
  );

  const handleEdgeClick: EdgeMouseHandler = useCallback(
    (_event, edge) => {
      onNodeSelect(null);
      const d = edge.data as { relationType?: string; strength?: number } | undefined;
      onEdgeSelect({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        relationType: d?.relationType ?? "UNKNOWN",
        strength: d?.strength ?? null,
      });
    },
    [onNodeSelect, onEdgeSelect],
  );

  const handlePaneClick = useCallback(() => {
    onNodeSelect(null);
    onEdgeSelect(null);
  }, [onNodeSelect, onEdgeSelect]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-500">
        Loading graph...
      </div>
    );
  }

  const totalRawEdges = (data?.edges ?? []).filter((e) => e.source && e.target).length;

  if (!data || totalRawEdges === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-sm text-slate-400">
        <p>No edges found in this namespace.</p>
        <p className="text-xs">
          {(data?.nodes ?? []).length} nodes exist but none are connected.
        </p>
      </div>
    );
  }

  return (
    <div className="relative h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onEdgeClick={handleEdgeClick}
        onPaneClick={handlePaneClick}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        minZoom={0.1}
        maxZoom={3}
      >
        <Background />
        <Controls />
        <MiniMap
          nodeColor={(n) => {
            const d = n.data as { memoryType?: string };
            const colors: Record<string, string> = {
              semantic: "#c084fc",
              episodic: "#60a5fa",
              procedural: "#34d399",
              prospective: "#fbbf24",
            };
            return colors[d.memoryType ?? ""] ?? "#e2e8f0";
          }}
        />
      </ReactFlow>

      {/* Stats badge + Random Pick */}
      <div className="absolute right-4 top-4 z-10 flex items-center gap-2">
        <div className="flex items-center gap-1.5 rounded-md bg-white/90 px-2.5 py-1.5 shadow-sm backdrop-blur dark:bg-slate-900/90">
          <button
            onClick={handleRandomPick}
            className="rounded bg-violet-100 px-2 py-0.5 text-[10px] font-medium text-violet-700 transition-colors hover:bg-violet-200 dark:bg-violet-900 dark:text-violet-300 dark:hover:bg-violet-800"
          >
            Random Pick
          </button>
          {pickedNodeId && (
            <button
              onClick={() => setPickedNodeId(null)}
              className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600 transition-colors hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700"
            >
              Show All
            </button>
          )}
          <span className="ml-1 text-[10px] text-slate-500">
            {nodes.length} nodes · {edges.length} edges
            {pickedNodeId && (
              <span> · picking {pickedNodeId.slice(0, 8)}...</span>
            )}
            {!pickedNodeId && nodes.length < (data?.nodes ?? []).length && (
              <span> · {(data?.nodes ?? []).length - nodes.length} hidden</span>
            )}
          </span>
        </div>
      </div>

      <EdgeLegend
        enabledTypes={enabledTypes}
        onToggle={handleToggleType}
        edgeCounts={edgeCounts}
      />
    </div>
  );
}
