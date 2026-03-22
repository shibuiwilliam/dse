"use client";

import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchCurationMemories } from "@/lib/api/curation";
import { InfoTip } from "@/components/ui/Tooltip";

export function ImportanceHeatmap({ namespace }: { namespace: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["importance-heatmap", namespace],
    queryFn: () => fetchCurationMemories({ namespace, pageSize: 100, sortBy: "importance" }),
  });

  if (isLoading) return <p className="text-sm text-slate-500">Loading...</p>;

  const memories = data?.memories ?? [];

  // Build histogram: bucket importance scores into 10 bins
  const bins = Array.from({ length: 10 }, (_, i) => ({
    range: `${(i * 10).toString()}–${((i + 1) * 10).toString()}%`,
    count: 0,
  }));

  for (const m of memories) {
    const idx = Math.min(9, Math.floor(m.importance_score * 10));
    bins[idx].count++;
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
        Importance Score Distribution
        <InfoTip text="Histogram of importance scores across all memories. Higher scores indicate knowledge the system considers more critical to retain." />
      </h3>
      <p className="mb-4 text-xs text-slate-500">
        {memories.length} memories in namespace
      </p>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={bins}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="range" tick={{ fontSize: 10 }} />
          <YAxis />
          <Tooltip />
          <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
