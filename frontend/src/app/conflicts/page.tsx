"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchConflicts, resolveConflict } from "@/lib/api/conflicts";
import { useNamespaceStore } from "@/stores/namespaceStore";
import { InfoTip } from "@/components/ui/Tooltip";
import { formatDistanceToNow } from "date-fns";

export default function ConflictsPage() {
  const namespace = useNamespaceStore((s) => s.namespace);
  const qc = useQueryClient();

  const { data: conflicts = [], isLoading } = useQuery({
    queryKey: ["conflicts", namespace],
    queryFn: () => fetchConflicts(namespace),
    refetchInterval: 10_000,
    enabled: !!namespace,
  });

  const resolveMutation = useMutation({
    mutationFn: ({ idA, idB, keep }: { idA: string; idB: string; keep: "A" | "B" | "both" }) =>
      resolveConflict(namespace, idA, idB, keep),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["conflicts"] }),
  });

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center gap-4">
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          Conflict Queue
          <InfoTip text="Pairs of memories detected as contradictory. Choose which to keep, or keep both. Auto-resolved conflicts (large confidence gap) are handled automatically." />
        </h1>
        {conflicts.length > 0 && (
          <span className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">
            {conflicts.length} pending
          </span>
        )}
      </div>

      {isLoading && <p className="text-sm text-slate-500">Loading...</p>}

      {!isLoading && conflicts.length === 0 && (
        <p className="text-sm text-slate-500">No pending conflicts.</p>
      )}

      <ul className="space-y-4">
        {conflicts.map((c) => (
          <li
            key={`${c.id_a}-${c.id_b}`}
            className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
          >
            <div className="mb-3 grid grid-cols-2 gap-4">
              <ConflictCard label="Memory A" memoryId={c.id_a} confidence={c.confidence_a} />
              <ConflictCard label="Memory B" memoryId={c.id_b} confidence={c.confidence_b} />
            </div>
            {c.detected_at && (
              <p className="mb-3 text-xs text-slate-400">
                Detected {formatDistanceToNow(new Date(c.detected_at), { addSuffix: true })}
              </p>
            )}
            <div className="flex gap-2">
              {(["A", "B", "both"] as const).map((keep) => (
                <button
                  key={keep}
                  onClick={() => resolveMutation.mutate({ idA: c.id_a, idB: c.id_b, keep })}
                  disabled={resolveMutation.isPending}
                  className="rounded-md bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-200 disabled:opacity-50 dark:bg-slate-800 dark:text-slate-300"
                >
                  {keep === "both" ? "Keep both" : `Keep ${keep}`}
                </button>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ConflictCard({
  label,
  memoryId,
  confidence,
}: {
  label: string;
  memoryId: string;
  confidence: number;
}) {
  return (
    <div className="rounded-md border border-slate-200 p-3 dark:border-slate-700">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-1 font-mono text-xs text-slate-600 dark:text-slate-400">
        {memoryId.slice(0, 16)}...
      </p>
      <div className="mt-2 flex items-center gap-2">
        <div className="h-1.5 flex-1 rounded-full bg-slate-200">
          <div
            className="h-1.5 rounded-full bg-emerald-500"
            style={{ width: `${confidence * 100}%` }}
          />
        </div>
        <span className="text-[10px] text-slate-500">{(confidence * 100).toFixed(0)}%</span>
      </div>
    </div>
  );
}
