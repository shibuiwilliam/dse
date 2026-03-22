"use client";

import { useQuery } from "@tanstack/react-query";
import { getMemory } from "@/lib/api/memories";
import type { Memory } from "@/lib/types";

const EDGE_COLORS: Record<string, { color: string; label: string; desc: string }> = {
  SUPERSEDED_BY: { color: "#f59e0b", label: "Superseded By", desc: "A was replaced by B (newer/better information)" },
  COMPLEMENTS: { color: "#10b981", label: "Complements", desc: "A and B together form more complete information" },
  CONTRADICTS: { color: "#ef4444", label: "Contradicts", desc: "A and B state conflicting facts (bidirectional)" },
  DERIVES: { color: "#6366f1", label: "Derives", desc: "B was inferred or summarized from A" },
  CAUSES: { color: "#8b5cf6", label: "Causes", desc: "A caused or triggered B" },
  REFERENCES: { color: "#64748b", label: "References", desc: "A cites or refers to B" },
  HAS_CHILD: { color: "#06b6d4", label: "Has Child", desc: "B is a part or sub-element of A" },
  TEMPORALLY_PRECEDES: { color: "#9ca3af", label: "Temporally Precedes", desc: "A happened before B" },
};

interface Props {
  sourceId: string;
  targetId: string;
  relationType: string;
  strength: number | null;
  onClose: () => void;
  onSelectNode: (id: string) => void;
}

export function EdgeDetailPanel({
  sourceId,
  targetId,
  relationType,
  strength,
  onClose,
  onSelectNode,
}: Props) {
  const source = useQuery({
    queryKey: ["memory-detail", sourceId],
    queryFn: () => getMemory(sourceId),
    enabled: !!sourceId,
  });

  const target = useQuery({
    queryKey: ["memory-detail", targetId],
    queryFn: () => getMemory(targetId),
    enabled: !!targetId,
  });

  const edgeInfo = EDGE_COLORS[relationType] ?? {
    color: "#94a3b8",
    label: relationType,
    desc: "",
  };

  return (
    <div className="flex h-full w-80 flex-col border-l border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-800">
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
          Edge Detail
        </h2>
        <button
          onClick={onClose}
          className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-5">
          {/* Relation type */}
          <div className="rounded-lg border p-4" style={{ borderColor: edgeInfo.color + "60" }}>
            <div className="mb-2 flex items-center gap-2">
              <span
                className="inline-block h-3 w-6 rounded-sm"
                style={{ background: edgeInfo.color }}
              />
              <span className="text-sm font-semibold" style={{ color: edgeInfo.color }}>
                {edgeInfo.label}
              </span>
            </div>
            <p className="text-xs leading-relaxed text-slate-500">{edgeInfo.desc}</p>
            {strength != null && (
              <div className="mt-3 flex items-center gap-2">
                <span className="text-[11px] text-slate-500">Strength</span>
                <div className="h-1.5 flex-1 rounded-full bg-slate-100 dark:bg-slate-800">
                  <div
                    className="h-1.5 rounded-full"
                    style={{ width: `${strength * 100}%`, background: edgeInfo.color }}
                  />
                </div>
                <span className="text-[10px] text-slate-500">
                  {(strength * 100).toFixed(0)}%
                </span>
              </div>
            )}
          </div>

          {/* Direction arrow */}
          <div className="flex items-center justify-center gap-2 text-xs text-slate-400">
            <span>Source</span>
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M5 12h14m-7-7l7 7-7 7" />
            </svg>
            <span>Target</span>
          </div>

          {/* Source node */}
          <EndpointCard
            label="Source"
            memoryId={sourceId}
            data={source.data}
            isLoading={source.isLoading}
            onClick={() => onSelectNode(sourceId)}
          />

          {/* Target node */}
          <EndpointCard
            label="Target"
            memoryId={targetId}
            data={target.data}
            isLoading={target.isLoading}
            onClick={() => onSelectNode(targetId)}
          />
        </div>
      </div>
    </div>
  );
}

const TYPE_COLORS: Record<string, string> = {
  semantic: "bg-purple-100 text-purple-700",
  episodic: "bg-blue-100 text-blue-700",
  procedural: "bg-emerald-100 text-emerald-700",
  prospective: "bg-amber-100 text-amber-700",
};

function EndpointCard({
  label,
  memoryId,
  data,
  isLoading,
  onClick,
}: {
  label: string;
  memoryId: string;
  data: Memory | undefined | null;
  isLoading: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full rounded-lg border border-slate-200 p-3 text-left transition-colors hover:border-violet-300 hover:bg-violet-50/50 dark:border-slate-800 dark:hover:border-violet-700 dark:hover:bg-violet-950/30"
    >
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      {isLoading && <p className="text-xs text-slate-400">Loading...</p>}
      {data && (
        <>
          <div className="mb-1.5 flex items-center gap-2">
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                TYPE_COLORS[data.memory_type] ?? "bg-slate-100 text-slate-600"
              }`}
            >
              {data.memory_type}
            </span>
            <span className="text-[10px] text-slate-400">
              conf {(data.confidence * 100).toFixed(0)}%
            </span>
          </div>
          <p className="line-clamp-3 text-xs leading-relaxed text-slate-700 dark:text-slate-300">
            {data.summary || data.content_text || ""}
          </p>
        </>
      )}
      <p className="mt-1.5 font-mono text-[9px] text-slate-400">{memoryId}</p>
      <p className="mt-0.5 text-[9px] text-violet-500">Click to view full details →</p>
    </button>
  );
}
