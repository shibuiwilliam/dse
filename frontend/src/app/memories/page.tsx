"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { retrieveMemories } from "@/lib/api/memories";
import { fetchMemoriesByRelation, type RelationSearchResult } from "@/lib/api/graph";
import { useNamespaceStore } from "@/stores/namespaceStore";
import { MemoryDetailPanel } from "@/components/ui/MemoryDetailPanel";
import { InfoTip } from "@/components/ui/Tooltip";
import type { ContextItem } from "@/lib/types";

const TYPE_COLORS: Record<string, string> = {
  semantic: "bg-purple-100 text-purple-700",
  episodic: "bg-blue-100 text-blue-700",
  procedural: "bg-emerald-100 text-emerald-700",
  prospective: "bg-amber-100 text-amber-700",
};

const RELATION_TYPES = [
  { value: "", label: "— Text search —" },
  { value: "SUPERSEDED_BY", label: "Superseded By" },
  { value: "COMPLEMENTS", label: "Complements" },
  { value: "CONTRADICTS", label: "Contradicts" },
  { value: "DERIVES", label: "Derives" },
  { value: "TEMPORALLY_PRECEDES", label: "Temporal" },
  { value: "CAUSES", label: "Causes" },
  { value: "HAS_CHILD", label: "Has Child" },
  { value: "REFERENCES", label: "References" },
] as const;

const EDGE_COLORS: Record<string, string> = {
  SUPERSEDED_BY: "bg-amber-100 text-amber-700",
  COMPLEMENTS: "bg-emerald-100 text-emerald-700",
  CONTRADICTS: "bg-red-100 text-red-700",
  DERIVES: "bg-indigo-100 text-indigo-700",
  TEMPORALLY_PRECEDES: "bg-slate-100 text-slate-600",
  CAUSES: "bg-purple-100 text-purple-700",
  HAS_CHILD: "bg-cyan-100 text-cyan-700",
  REFERENCES: "bg-slate-200 text-slate-700",
};

/** Unified result type for both search modes */
interface DisplayItem {
  id: string;
  memory_type: string;
  content: string;
  confidence: number;
  score?: number;
  tier?: string;
  tokens?: number;
  edge?: string;
}

export default function MemoriesPage() {
  const [query, setQuery] = useState("");
  const [relationFilter, setRelationFilter] = useState("");
  const namespace = useNamespaceStore((s) => s.namespace);
  const [results, setResults] = useState<DisplayItem[]>([]);
  const [totalTokens, setTotalTokens] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [resultLabel, setResultLabel] = useState("");

  // Text search mode
  const textSearch = useMutation({
    mutationFn: () => retrieveMemories({ query, namespace }),
    onSuccess: (data) => {
      setResults(
        data.items.map((item: ContextItem) => ({
          id: item.memory_id,
          memory_type: item.memory_type,
          content: item.content,
          confidence: item.confidence,
          score: item.score,
          tier: item.tier,
          tokens: item.tokens,
        })),
      );
      setTotalTokens(data.total_tokens);
      setResultLabel(`${data.items.length} results — ${data.total_tokens} tokens used`);
      setSelectedId(null);
    },
  });

  // Edge search mode
  const edgeSearch = useMutation({
    mutationFn: () => fetchMemoriesByRelation(namespace, relationFilter),
    onSuccess: (data) => {
      setResults(
        data.memories.map((m: RelationSearchResult) => ({
          id: m.id,
          memory_type: m.memory_type,
          content: m.summary ?? m.content_text ?? "",
          confidence: m.confidence,
          score: m.importance_score ?? m.importance,
          edge: data.relation_type,
        })),
      );
      setTotalTokens(0);
      setResultLabel(
        `${data.memories.length} memories with ${data.relation_type} edge`,
      );
      setSelectedId(null);
    },
  });

  const isSearching = textSearch.isPending || edgeSearch.isPending;
  const isEdgeMode = relationFilter !== "";

  const handleSearch = () => {
    if (isEdgeMode) {
      edgeSearch.mutate();
    } else if (query) {
      textSearch.mutate();
    }
  };

  return (
    <div className="flex h-full">
      {/* Left: search + results list */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="border-b border-slate-200 p-6 pb-4 dark:border-slate-800">
          <h1 className="mb-4 flex items-center gap-2 text-2xl font-semibold">
            Memory Search
            <InfoTip text="Search memories by text query or by edge type. Select a relation type to find all memories connected by that edge." />
          </h1>

          <div className="flex gap-3">
            {/* Relation type selector */}
            <select
              value={relationFilter}
              onChange={(e) => {
                setRelationFilter(e.target.value);
                setResults([]);
                setResultLabel("");
              }}
              className="w-44 rounded-md border border-slate-300 px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
            >
              {RELATION_TYPES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>

            {/* Text query input (disabled in edge mode) */}
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !isEdgeMode && query && handleSearch()}
              placeholder={isEdgeMode ? "(edge filter active)" : "Search memories..."}
              disabled={isEdgeMode}
              className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm disabled:opacity-40 dark:border-slate-700 dark:bg-slate-900"
            />

            <button
              onClick={handleSearch}
              disabled={isSearching || (!isEdgeMode && !query)}
              className="rounded-md bg-violet-600 px-5 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
            >
              {isSearching ? "Searching..." : "Search"}
            </button>
          </div>

          {resultLabel && (
            <p className="mt-2 text-xs text-slate-500">{resultLabel}</p>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-6 pt-4">
          {results.length === 0 && !isSearching && (
            <p className="text-sm text-slate-400">
              {resultLabel
                ? "No results found."
                : isEdgeMode
                  ? "Click Search to find memories with this edge type."
                  : "Enter a query to search memories."}
            </p>
          )}

          <div className="space-y-2">
            {results.map((item) => {
              const isSelected = item.id === selectedId;
              return (
                <button
                  key={item.id}
                  onClick={() => setSelectedId(isSelected ? null : item.id)}
                  className={`w-full rounded-lg border p-4 text-left transition-all ${
                    isSelected
                      ? "border-violet-400 bg-violet-50 ring-1 ring-violet-400 dark:border-violet-600 dark:bg-violet-950"
                      : "border-slate-200 bg-white hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700"
                  }`}
                >
                  <div className="mb-2 flex items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        TYPE_COLORS[item.memory_type] ?? "bg-slate-100"
                      }`}
                    >
                      {item.memory_type}
                    </span>
                    {item.edge && (
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          EDGE_COLORS[item.edge] ?? "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {item.edge}
                      </span>
                    )}
                    {item.tier && (
                      <span className="text-xs text-slate-400">{item.tier}</span>
                    )}
                    <span className="ml-auto text-xs text-slate-400">
                      {item.score != null && `score ${item.score.toFixed(3)} · `}
                      conf {(item.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="line-clamp-3 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                    {item.content}
                  </p>
                  <p className="mt-2 font-mono text-[10px] text-slate-400">
                    {item.id}
                  </p>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Right: detail panel */}
      {selectedId && (
        <MemoryDetailPanel memoryId={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  );
}
