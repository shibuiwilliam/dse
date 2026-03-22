"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { retrieveMemories } from "@/lib/api/memories";
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

export default function MemoriesPage() {
  const [query, setQuery] = useState("");
  const namespace = useNamespaceStore((s) => s.namespace);
  const [results, setResults] = useState<ContextItem[]>([]);
  const [totalTokens, setTotalTokens] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const searchMutation = useMutation({
    mutationFn: () => retrieveMemories({ query, namespace }),
    onSuccess: (data) => {
      setResults(data.items);
      setTotalTokens(data.total_tokens);
      setSelectedId(null);
    },
  });

  return (
    <div className="flex h-full">
      {/* Left: search + results list */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="border-b border-slate-200 p-6 pb-4 dark:border-slate-800">
          <h1 className="mb-4 flex items-center gap-2 text-2xl font-semibold">
            Memory Search
            <InfoTip text="Search and retrieve memories using the cascade retrieval pipeline. Results are ranked by relevance, confidence, and recency within a token budget." />
          </h1>
          <div className="flex gap-3">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && query && searchMutation.mutate()}
              placeholder="Search memories..."
              className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
            />
            <button
              onClick={() => searchMutation.mutate()}
              disabled={searchMutation.isPending || !query}
              className="rounded-md bg-violet-600 px-5 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
            >
              {searchMutation.isPending ? "Searching..." : "Search"}
            </button>
          </div>
          {totalTokens > 0 && (
            <p className="mt-2 text-xs text-slate-500">
              {results.length} results — {totalTokens} tokens used
            </p>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-6 pt-4">
          {results.length === 0 && !searchMutation.isPending && (
            <p className="text-sm text-slate-400">
              {totalTokens > 0 ? "No results found." : "Enter a query to search memories."}
            </p>
          )}

          <div className="space-y-2">
            {results.map((item) => {
              const isSelected = item.memory_id === selectedId;
              return (
                <button
                  key={item.memory_id}
                  onClick={() => setSelectedId(isSelected ? null : item.memory_id)}
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
                    <span className="text-xs text-slate-400">{item.tier}</span>
                    <span className="ml-auto text-xs text-slate-400">
                      score {item.score.toFixed(3)} · conf {(item.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="line-clamp-3 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                    {item.content}
                  </p>
                  <p className="mt-2 font-mono text-[10px] text-slate-400">
                    {item.memory_id}
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
