"use client";

import { useQuery } from "@tanstack/react-query";
import { InfoTip } from "@/components/ui/Tooltip";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchCurationStats } from "@/lib/api/curation";

const TYPE_COLORS: Record<string, string> = {
  semantic: "#c084fc",
  episodic: "#60a5fa",
  procedural: "#34d399",
  prospective: "#fbbf24",
};

const DECAY_COLORS = { active: "#34d399", warm: "#fbbf24", archive: "#94a3b8" };

export function ImportanceChart({ namespace }: { namespace: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["curation-stats", namespace],
    queryFn: () => fetchCurationStats(namespace),
  });

  if (isLoading || !data) {
    return <p className="text-sm text-slate-500">Loading analytics...</p>;
  }

  const typeData = Object.entries(data.memory_type_distribution).map(([name, value]) => ({
    name,
    value,
  }));

  const decayData = Object.entries(data.decay_distribution).map(([name, value]) => ({
    name,
    value,
  }));

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold">
          Memory Type Distribution
          <InfoTip text="Pie chart breakdown: Episodic (experiences), Semantic (facts), Procedural (skills), Prospective (reminders)." />
        </h3>
        <ResponsiveContainer width="100%" height={250}>
          <PieChart>
            <Pie
              data={typeData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={90}
              label={({ name, value }) => `${name}: ${value}`}
            >
              {typeData.map((entry) => (
                <Cell key={entry.name} fill={TYPE_COLORS[entry.name] ?? "#94a3b8"} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold">
          Decay Distribution
          <InfoTip text="Active (decay > 0.4): fresh memories. Warm (0.2-0.4): fading. Archive (< 0.2): rarely retrieved." />
        </h3>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={decayData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="value">
              {decayData.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={DECAY_COLORS[entry.name as keyof typeof DECAY_COLORS] ?? "#94a3b8"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900 lg:col-span-2">
        <h3 className="mb-3 text-sm font-semibold">Summary</h3>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-2xl font-bold">{data.total_memories}</p>
            <p className="text-xs text-slate-500">Total memories</p>
          </div>
          <div>
            <p className="text-2xl font-bold">{(data.avg_importance * 100).toFixed(0)}%</p>
            <p className="text-xs text-slate-500">Avg importance</p>
          </div>
          <div>
            <p className="text-2xl font-bold">{data.decay_distribution.active}</p>
            <p className="text-xs text-slate-500">Active memories</p>
          </div>
        </div>
      </div>
    </div>
  );
}
