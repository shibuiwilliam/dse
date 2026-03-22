"use client";

import { useCallback, useState } from "react";
import { useNamespaceStore } from "@/stores/namespaceStore";
import { MemoryGraph, type SelectedEdge } from "./components/MemoryGraph";
import { MemoryDetailPanel } from "@/components/ui/MemoryDetailPanel";
import { EdgeDetailPanel } from "@/components/ui/EdgeDetailPanel";
import { InfoTip } from "@/components/ui/Tooltip";

export default function GraphPage() {
  const namespace = useNamespaceStore((s) => s.namespace);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<SelectedEdge | null>(null);

  const handleNodeSelect = useCallback((nodeId: string | null) => {
    setSelectedNodeId(nodeId);
    if (nodeId) setSelectedEdge(null);
  }, []);

  const handleEdgeSelect = useCallback((edge: SelectedEdge | null) => {
    setSelectedEdge(edge);
    if (edge) setSelectedNodeId(null);
  }, []);

  const handleClosePanel = useCallback(() => {
    setSelectedNodeId(null);
    setSelectedEdge(null);
  }, []);

  // When clicking a node from within the edge panel, switch to node view
  const handleEdgePanelNodeClick = useCallback((nodeId: string) => {
    setSelectedEdge(null);
    setSelectedNodeId(nodeId);
  }, []);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-slate-200 px-6 py-3 dark:border-slate-800">
        <h1 className="flex items-center gap-2 text-lg font-semibold">
          Memory Graph
          <InfoTip text="Interactive knowledge graph of memory relationships. Click nodes to inspect memories, click edges to see relationship details. Drag to pan, scroll to zoom." />
        </h1>
        {selectedNodeId && (
          <span className="rounded bg-violet-100 px-2 py-0.5 font-mono text-[10px] text-violet-700 dark:bg-violet-900 dark:text-violet-300">
            Node: {selectedNodeId.slice(0, 12)}...
          </span>
        )}
        {selectedEdge && (
          <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
            Edge: {selectedEdge.relationType}
          </span>
        )}
      </div>
      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1">
          {namespace ? (
            <MemoryGraph
              namespace={namespace}
              selectedNodeId={selectedNodeId}
              onNodeSelect={handleNodeSelect}
              onEdgeSelect={handleEdgeSelect}
            />
          ) : (
            <p className="p-6 text-sm text-slate-500">Select a namespace from the sidebar.</p>
          )}
        </div>
        {selectedNodeId && (
          <MemoryDetailPanel memoryId={selectedNodeId} onClose={handleClosePanel} />
        )}
        {selectedEdge && (
          <EdgeDetailPanel
            sourceId={selectedEdge.source}
            targetId={selectedEdge.target}
            relationType={selectedEdge.relationType}
            strength={selectedEdge.strength}
            onClose={handleClosePanel}
            onSelectNode={handleEdgePanelNodeClick}
          />
        )}
      </div>
    </div>
  );
}
