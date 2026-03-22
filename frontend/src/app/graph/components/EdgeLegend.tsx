"use client";

export const ALL_EDGE_TYPES = [
  { type: "SUPERSEDED_BY", color: "#f59e0b", label: "Superseded" },
  { type: "COMPLEMENTS", color: "#10b981", label: "Complements" },
  { type: "CONTRADICTS", color: "#ef4444", label: "Contradicts" },
  { type: "DERIVES", color: "#6366f1", label: "Derives" },
  { type: "CAUSES", color: "#8b5cf6", label: "Causes" },
  { type: "REFERENCES", color: "#64748b", label: "References" },
  { type: "HAS_CHILD", color: "#06b6d4", label: "Has child" },
  { type: "TEMPORALLY_PRECEDES", color: "#d1d5db", label: "Temporal" },
] as const;

interface Props {
  enabledTypes: Set<string>;
  onToggle: (type: string) => void;
  edgeCounts: Record<string, number>;
}

export function EdgeLegend({ enabledTypes, onToggle, edgeCounts }: Props) {
  const totalEdges = Object.values(edgeCounts).reduce((a, b) => a + b, 0);

  return (
    <div className="absolute bottom-4 left-4 z-10 rounded-lg border border-slate-200 bg-white/95 p-3 text-xs shadow-md backdrop-blur dark:border-slate-700 dark:bg-slate-900/95">
      <div className="mb-2 flex items-center justify-between">
        <p className="font-semibold text-slate-600 dark:text-slate-400">
          Edge Filter
        </p>
        <span className="text-[10px] text-slate-400">{totalEdges} edges</span>
      </div>
      <div className="space-y-0.5">
        {ALL_EDGE_TYPES.map((e) => {
          const count = edgeCounts[e.type] ?? 0;
          const enabled = enabledTypes.has(e.type);
          return (
            <button
              key={e.type}
              onClick={() => onToggle(e.type)}
              className={`flex w-full items-center gap-2 rounded px-1.5 py-1 text-left transition-all ${
                enabled
                  ? "bg-white dark:bg-slate-800"
                  : "opacity-40 hover:opacity-60"
              }`}
            >
              <span
                className="inline-block h-2.5 w-5 rounded-sm transition-all"
                style={{
                  background: enabled ? e.color : "#cbd5e1",
                }}
              />
              <span
                className={`flex-1 ${
                  enabled
                    ? "text-slate-700 dark:text-slate-300"
                    : "text-slate-400 line-through"
                }`}
              >
                {e.label}
              </span>
              {count > 0 && (
                <span className="tabular-nums text-[10px] text-slate-400">
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>
      <div className="mt-2 flex gap-1 border-t border-slate-100 pt-2 dark:border-slate-800">
        <button
          onClick={() => ALL_EDGE_TYPES.forEach((e) => !enabledTypes.has(e.type) && onToggle(e.type))}
          className="flex-1 rounded bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400"
        >
          All
        </button>
        <button
          onClick={() => ALL_EDGE_TYPES.forEach((e) => enabledTypes.has(e.type) && onToggle(e.type))}
          className="flex-1 rounded bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400"
        >
          None
        </button>
      </div>
    </div>
  );
}
