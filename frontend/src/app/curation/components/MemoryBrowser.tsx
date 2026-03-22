"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchCurationMemories, forgetMemory, pinMemory } from "@/lib/api/curation";
import type { Memory } from "@/lib/types";
import { MemoryEditor } from "./MemoryEditor";

const TYPE_COLORS: Record<string, string> = {
  semantic: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  episodic: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  procedural: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
  prospective: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
};

export function MemoryBrowser({ namespace }: { namespace: string }) {
  const qc = useQueryClient();
  const [filter, setFilter] = useState({ memoryType: "all", sortBy: "importance" });
  const [editing, setEditing] = useState<Memory | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["curation-memories", namespace, filter],
    queryFn: () =>
      fetchCurationMemories({ namespace, memoryType: filter.memoryType, sortBy: filter.sortBy }),
  });

  const pin = useMutation({
    mutationFn: ({ id, pinned }: { id: string; pinned: boolean }) => pinMemory(id, pinned),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["curation-memories"] }),
  });

  const forget = useMutation({
    mutationFn: (id: string) => forgetMemory(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["curation-memories"] }),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <select
          value={filter.memoryType}
          onChange={(e) => setFilter((f) => ({ ...f, memoryType: e.target.value }))}
          className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
        >
          <option value="all">All types</option>
          <option value="semantic">Semantic</option>
          <option value="episodic">Episodic</option>
          <option value="procedural">Procedural</option>
          <option value="prospective">Prospective</option>
        </select>
        <select
          value={filter.sortBy}
          onChange={(e) => setFilter((f) => ({ ...f, sortBy: e.target.value }))}
          className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
        >
          <option value="importance">Importance</option>
          <option value="created_at">Created</option>
          <option value="decay_score">Decay</option>
        </select>
      </div>

      {isLoading && <p className="text-sm text-slate-500">Loading...</p>}

      <ul className="divide-y divide-slate-100 dark:divide-slate-800">
        {(data?.memories ?? []).map((m) => (
          <li key={m.id} className="flex items-start gap-4 py-4">
            <div className="min-w-0 flex-1">
              <div className="mb-1 flex items-center gap-2">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    TYPE_COLORS[m.memory_type] ?? "bg-slate-100 text-slate-600"
                  }`}
                >
                  {m.memory_type}
                </span>
                <span className="font-mono text-[10px] text-slate-400">{m.id.slice(0, 12)}...</span>
              </div>
              <p className="line-clamp-2 text-sm text-slate-800 dark:text-slate-200">
                {m.summary || m.content_text}
              </p>
              <div className="mt-1.5 flex gap-4 text-[11px] text-slate-400">
                <span>Importance {(m.importance_score * 100).toFixed(0)}%</span>
                <span>Decay {(m.decay_score * 100).toFixed(0)}%</span>
                <span>Confidence {(m.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
            <div className="flex shrink-0 gap-1.5">
              <button
                onClick={() => setEditing(m)}
                className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400"
              >
                Edit
              </button>
              <button
                onClick={() => pin.mutate({ id: m.id, pinned: true })}
                className="rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-700 hover:bg-amber-100 dark:bg-amber-900 dark:text-amber-300"
              >
                Pin
              </button>
              <button
                onClick={() => forget.mutate(m.id)}
                className="rounded-md bg-red-50 px-2 py-1 text-xs text-red-700 hover:bg-red-100 dark:bg-red-900 dark:text-red-300"
              >
                Forget
              </button>
            </div>
          </li>
        ))}
      </ul>

      {data && <p className="text-xs text-slate-400">{data.total} memories total</p>}

      {editing && (
        <MemoryEditor
          memory={editing}
          open={!!editing}
          onOpenChange={(open) => { if (!open) setEditing(null); }}
        />
      )}
    </div>
  );
}
