"use client";

import { useQuery } from "@tanstack/react-query";
import { getMemory } from "@/lib/api/memories";
import { fetchNeighbors } from "@/lib/api/graph";

const TYPE_COLORS: Record<string, string> = {
  semantic: "bg-purple-100 text-purple-700",
  episodic: "bg-blue-100 text-blue-700",
  procedural: "bg-emerald-100 text-emerald-700",
  prospective: "bg-amber-100 text-amber-700",
};

const EDGE_COLORS: Record<string, string> = {
  SUPERSEDED_BY: "text-amber-600",
  COMPLEMENTS: "text-emerald-600",
  CONTRADICTS: "text-red-600",
  DERIVES: "text-indigo-600",
  CAUSES: "text-violet-600",
  REFERENCES: "text-slate-600",
  HAS_CHILD: "text-cyan-600",
  TEMPORALLY_PRECEDES: "text-slate-400",
};

interface Props {
  memoryId: string;
  onClose: () => void;
}

export function MemoryDetailPanel({ memoryId, onClose }: Props) {
  const memory = useQuery({
    queryKey: ["memory-detail", memoryId],
    queryFn: () => getMemory(memoryId),
    enabled: !!memoryId,
  });

  const neighbors = useQuery({
    queryKey: ["node-neighbors", memoryId],
    queryFn: () => fetchNeighbors(memoryId, 1, 20),
    enabled: !!memoryId,
  });

  const m = memory.data;

  return (
    <div className="flex h-full w-80 flex-col border-l border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-800">
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
          Memory Detail
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
        {memory.isLoading && (
          <p className="text-xs text-slate-400">Loading...</p>
        )}

        {m && (
          <div className="space-y-4">
            {/* Type + ID */}
            <div>
              <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_COLORS[m.memory_type] ?? "bg-slate-100 text-slate-600"}`}>
                {m.memory_type}
              </span>
              <p className="mt-1.5 font-mono text-[10px] text-slate-400 break-all">{m.id}</p>
            </div>

            {/* Summary */}
            <Section label="Summary">
              <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                {m.summary || "(no summary)"}
              </p>
            </Section>

            {/* Content */}
            {m.content_text && m.content_text !== m.summary && (
              <Section label="Content">
                <p className="max-h-40 overflow-y-auto text-xs leading-relaxed text-slate-600 dark:text-slate-400">
                  {m.content_text}
                </p>
              </Section>
            )}

            {/* Scores */}
            <Section label="Scores">
              <ScoreBar label="Confidence" value={m.confidence} color="#8b5cf6" />
              <ScoreBar label="Importance" value={m.importance_score} color="#10b981" />
              <ScoreBar label="Decay" value={m.decay_score} color="#f59e0b" />
            </Section>

            {/* Metadata */}
            <Section label="Metadata">
              <MetaRow label="Namespace" value={m.namespace} />
              <MetaRow label="Source" value={m.source_type} />
              <MetaRow label="Status" value={m.verification_status} />
              <MetaRow label="Created" value={new Date(m.created_at).toLocaleDateString()} />
              {m.superseded_by && <MetaRow label="Superseded by" value={m.superseded_by.slice(0, 12) + "..."} />}
              {m.is_archived && <MetaRow label="Archived" value="Yes" />}
            </Section>

            {/* Tags */}
            {m.tags.length > 0 && (
              <Section label="Tags">
                <div className="flex flex-wrap gap-1">
                  {m.tags.map((t) => (
                    <span key={t} className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                      {t}
                    </span>
                  ))}
                </div>
              </Section>
            )}

            {/* Entities */}
            {m.entities.length > 0 && (
              <Section label="Entities">
                <div className="flex flex-wrap gap-1">
                  {m.entities.map((e) => (
                    <span key={e} className="rounded bg-violet-50 px-1.5 py-0.5 text-[10px] font-medium text-violet-700 dark:bg-violet-950 dark:text-violet-300">
                      {e}
                    </span>
                  ))}
                </div>
              </Section>
            )}

            {/* Graph neighbors */}
            <Section label={`Relations (${(neighbors.data as unknown[])?.length ?? 0})`}>
              {neighbors.isLoading && <p className="text-[10px] text-slate-400">Loading...</p>}
              {(neighbors.data ?? []).length === 0 && !neighbors.isLoading && (
                <p className="text-[10px] text-slate-400">No relations.</p>
              )}
              <ul className="space-y-1">
                {(neighbors.data ?? []).map((n, i) => (
                  <li key={i} className="flex items-center gap-2 text-[11px]">
                    <span className={`font-medium ${EDGE_COLORS[n.relation_type] ?? "text-slate-500"}`}>
                      {n.relation_type}
                    </span>
                    <span className="truncate font-mono text-[10px] text-slate-400">
                      {n.id.slice(0, 12)}...
                    </span>
                  </li>
                ))}
              </ul>
            </Section>
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      {children}
    </div>
  );
}

function ScoreBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-2 py-0.5">
      <span className="w-20 text-[11px] text-slate-500">{label}</span>
      <div className="h-1.5 flex-1 rounded-full bg-slate-100 dark:bg-slate-800">
        <div
          className="h-1.5 rounded-full transition-all"
          style={{ width: `${value * 100}%`, background: color }}
        />
      </div>
      <span className="w-8 text-right text-[10px] text-slate-500">
        {(value * 100).toFixed(0)}%
      </span>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-0.5 text-[11px]">
      <span className="text-slate-500">{label}</span>
      <span className="font-mono text-slate-700 dark:text-slate-300">{value}</span>
    </div>
  );
}
