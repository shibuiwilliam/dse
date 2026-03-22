"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchProspective } from "@/lib/api/curation";
import { InfoTip } from "@/components/ui/Tooltip";
import { formatDistanceToNow } from "date-fns";
import type { Memory } from "@/lib/types";

export function ProspectiveList({ namespace }: { namespace: string }) {
  const pending = useQuery({
    queryKey: ["prospective", namespace, "pending"],
    queryFn: () => fetchProspective(namespace, "pending"),
  });

  const triggered = useQuery({
    queryKey: ["prospective", namespace, "triggered"],
    queryFn: () => fetchProspective(namespace, "triggered"),
  });

  return (
    <div className="space-y-6">
      <Section
        title="Pending"
        tip="Prospective memories waiting for their trigger condition (time, event, or custom condition) to be met."
        items={pending.data ?? []}
        loading={pending.isLoading}
        badge="amber"
      />
      <Section
        title="Triggered"
        tip="Prospective memories whose conditions have fired. These will auto-archive after the configured retention period."
        items={triggered.data ?? []}
        loading={triggered.isLoading}
        badge="emerald"
      />
    </div>
  );
}

function Section({
  title,
  tip,
  items,
  loading,
  badge,
}: {
  title: string;
  tip?: string;
  items: Memory[];
  loading: boolean;
  badge: string;
}) {
  const badgeClass =
    badge === "amber"
      ? "bg-amber-100 text-amber-700"
      : "bg-emerald-100 text-emerald-700";

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        {tip && <InfoTip text={tip} />}
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${badgeClass}`}>
          {items.length}
        </span>
      </div>
      {loading && <p className="text-sm text-slate-500">Loading...</p>}
      {!loading && items.length === 0 && (
        <p className="text-sm text-slate-400">None.</p>
      )}
      <ul className="space-y-2">
        {items.map((m) => (
          <li
            key={m.id}
            className="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800"
          >
            <p className="font-medium text-slate-800 dark:text-slate-200">
              {m.summary}
            </p>
            <div className="mt-1 flex gap-3 text-[11px] text-slate-400">
              <span>Trigger: {m.trigger_type ?? "—"}</span>
              {m.trigger_at && (
                <span>
                  At: {formatDistanceToNow(new Date(m.trigger_at), { addSuffix: true })}
                </span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
