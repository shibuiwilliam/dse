"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchCurationMemories } from "@/lib/api/curation";
import { InfoTip } from "@/components/ui/Tooltip";

export function CompressionHistory({ namespace }: { namespace: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["compression-history", namespace],
    queryFn: () =>
      fetchCurationMemories({ namespace, memoryType: "semantic", sortBy: "created_at" }),
  });

  if (isLoading) return <p className="text-sm text-slate-500">Loading...</p>;

  const semantics = data?.memories ?? [];

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
        Compression History
        <InfoTip text="Semantic memories created by compressing clusters of similar episodic memories. Each represents generalized knowledge distilled from multiple experiences." />
      </h3>
      <p className="mb-3 text-xs text-slate-500">
        Semantic memories created by compression ({semantics.length} total)
      </p>
      {semantics.length === 0 ? (
        <p className="text-sm text-slate-400">No compressed memories yet.</p>
      ) : (
        <ul className="space-y-2">
          {semantics.slice(0, 20).map((m) => (
            <li
              key={m.id}
              className="rounded-md border border-purple-100 bg-purple-50/50 p-3 dark:border-purple-900 dark:bg-purple-950/30"
            >
              <p className="text-sm text-slate-700 dark:text-slate-300">{m.summary}</p>
              <div className="mt-1 flex gap-3 text-[10px] text-slate-400">
                <span>Confidence {(m.confidence * 100).toFixed(0)}%</span>
                <span>Importance {(m.importance_score * 100).toFixed(0)}%</span>
                <span className="font-mono">{m.id.slice(0, 8)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
