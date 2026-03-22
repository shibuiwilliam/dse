"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchCurationStats } from "@/lib/api/curation";
import { fetchConflicts } from "@/lib/api/conflicts";
import { useNamespaceStore } from "@/stores/namespaceStore";
import { InfoTip } from "@/components/ui/Tooltip";

export default function DashboardPage() {
  const namespace = useNamespaceStore((s) => s.namespace);

  const stats = useQuery({
    queryKey: ["stats", namespace],
    queryFn: () => fetchCurationStats(namespace),
    enabled: !!namespace,
  });
  const conflicts = useQuery({
    queryKey: ["conflicts", namespace],
    queryFn: () => fetchConflicts(namespace),
    enabled: !!namespace,
  });

  return (
    <div className="p-6">
      <h1 className="mb-6 flex items-center gap-2 text-2xl font-semibold">
        Dashboard
        <InfoTip text="Overview of memory statistics for the selected namespace. Shows total count, average importance, active memories, and pending contradictions." />
      </h1>

      {!namespace && (
        <p className="text-sm text-slate-500">Select a namespace from the sidebar.</p>
      )}

      <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard
          label="Total Memories"
          value={stats.data?.total_memories ?? "—"}
          color="violet"
          tip="Total number of memory records stored in this namespace."
        />
        <StatCard
          label="Avg Importance"
          value={stats.data ? `${(stats.data.avg_importance * 100).toFixed(0)}%` : "—"}
          color="emerald"
          tip="Average importance score (0-100%) across all memories. Higher means more critical knowledge."
        />
        <StatCard
          label="Active"
          value={stats.data?.decay_distribution.active ?? "—"}
          color="blue"
          tip="Memories with decay score > 0.4. These are fresh and readily retrieved."
        />
        <StatCard
          label="Pending Conflicts"
          value={conflicts.data?.length ?? "—"}
          color="red"
          tip="Memory pairs detected as contradictory that need manual resolution."
        />
      </div>

      {stats.data && (
        <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-500">
            Memory Type Distribution
            <InfoTip text="Breakdown by cognitive type: Episodic (experiences), Semantic (facts), Procedural (how-to), Prospective (future reminders)." />
          </h2>
          <div className="flex gap-3">
            {Object.entries(stats.data.memory_type_distribution).map(([type, count]) => (
              <TypeBadge key={type} type={type} count={count} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
  tip,
}: {
  label: string;
  value: string | number;
  color: string;
  tip?: string;
}) {
  const colors: Record<string, string> = {
    violet: "border-violet-200 bg-violet-50 dark:border-violet-900 dark:bg-violet-950",
    emerald: "border-emerald-200 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950",
    blue: "border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950",
    red: "border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950",
  };
  return (
    <div className={`rounded-lg border p-4 ${colors[color] ?? ""}`}>
      <p className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
        {label}
        {tip && <InfoTip text={tip} position="bottom" />}
      </p>
      <p className="mt-1 text-2xl font-bold">{value}</p>
    </div>
  );
}

function TypeBadge({ type, count }: { type: string; count: number }) {
  const colors: Record<string, string> = {
    semantic: "bg-purple-100 text-purple-700",
    episodic: "bg-blue-100 text-blue-700",
    procedural: "bg-emerald-100 text-emerald-700",
    prospective: "bg-amber-100 text-amber-700",
  };
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-medium ${colors[type] ?? "bg-slate-100 text-slate-600"}`}>
      {type}: {count}
    </span>
  );
}
