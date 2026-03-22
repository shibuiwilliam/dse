"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchSubgraph } from "@/lib/api/graph";
import { InfoTip } from "@/components/ui/Tooltip";

const EDGE_LABELS: Record<string, { label: string; color: string }> = {
  SUPERSEDED_BY: { label: "Superseded", color: "text-amber-600" },
  COMPLEMENTS: { label: "Complements", color: "text-emerald-600" },
  CONTRADICTS: { label: "Contradicts", color: "text-red-600" },
  DERIVES: { label: "Derives", color: "text-indigo-600" },
  CAUSES: { label: "Causes", color: "text-violet-600" },
  REFERENCES: { label: "References", color: "text-slate-600" },
  HAS_CHILD: { label: "Has child", color: "text-cyan-600" },
  TEMPORALLY_PRECEDES: { label: "Temporal", color: "text-slate-400" },
};

export function DiscoveryLog({ namespace }: { namespace: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["discovery-log", namespace],
    queryFn: () => fetchSubgraph(namespace, 200),
    refetchInterval: 30_000,
  });

  if (isLoading) return <p className="text-sm text-slate-500">Loading...</p>;

  const edges = data?.edges ?? [];
  const edgeTypeCounts: Record<string, number> = {};
  for (const e of edges) {
    edgeTypeCounts[e.relation_type] = (edgeTypeCounts[e.relation_type] ?? 0) + 1;
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
        Relation Discovery Log
        <InfoTip text="Counts of automatically discovered relationships between memories. The LLM classifies pairs as complementary, contradictory, causal, etc." />
      </h3>
      <p className="mb-3 text-xs text-slate-500">
        {edges.length} edges discovered across {data?.nodes.length ?? 0} nodes
      </p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {Object.entries(edgeTypeCounts).map(([type, count]) => {
          const info = EDGE_LABELS[type] ?? { label: type, color: "text-slate-600" };
          return (
            <div key={type} className="rounded-md border border-slate-100 p-2 text-center dark:border-slate-800">
              <p className={`text-lg font-bold ${info.color}`}>{count}</p>
              <p className="text-[10px] text-slate-500">{info.label}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
