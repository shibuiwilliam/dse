"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNamespaceStore } from "@/stores/namespaceStore";
import {
  createNamespace,
  deleteNamespace,
  fetchNamespaces,
  fetchNamespaceStats,
} from "@/lib/api/namespaces";
import { InfoTip } from "@/components/ui/Tooltip";

export default function SettingsPage() {
  const { namespace, available } = useNamespaceStore();

  return (
    <div className="p-6">
      <h1 className="mb-6 flex items-center gap-2 text-2xl font-semibold">
        Settings
        <InfoTip text="Manage namespaces (create, delete, view stats) and check the status of connected infrastructure services." />
      </h1>
      <div className="space-y-6">
        <NamespaceManager />

        <Section title="Active Namespace">
          <ConfigRow label="Current" value={namespace || "(none)"} />
          <ConfigRow label="Total namespaces" value={String(available.length)} />
          {namespace && <NamespaceStatsPanel namespace={namespace} />}
        </Section>

        <Section title="Service Status">
          <StatusRow label="API Server" url="http://localhost:8000" />
          <StatusRow label="Elasticsearch" url="http://localhost:9200" />
          <StatusRow label="Neo4j" url="http://localhost:7474" />
          <StatusRow label="Temporal" url="http://localhost:8080" />
          <StatusRow label="MinIO" url="http://localhost:9001" />
          <StatusRow label="Redpanda" url="http://localhost:8085" />
        </Section>
      </div>
    </div>
  );
}

function NamespaceManager() {
  const qc = useQueryClient();
  const { setAvailable, setNamespace: selectNamespace } = useNamespaceStore();
  const [newNs, setNewNs] = useState("");

  const { data: namespaces = [] } = useQuery({
    queryKey: ["namespaces"],
    queryFn: fetchNamespaces,
  });

  const create = useMutation({
    mutationFn: () => createNamespace(newNs.trim()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["namespaces"] });
      selectNamespace(newNs.trim());
      setNewNs("");
    },
  });

  const remove = useMutation({
    mutationFn: (ns: string) => deleteNamespace(ns),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["namespaces"] });
    },
  });

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
      <h2 className="mb-3 text-sm font-semibold text-slate-600 dark:text-slate-400">
        Namespace Management
      </h2>

      <div className="mb-4 flex gap-2">
        <input
          type="text"
          value={newNs}
          onChange={(e) => setNewNs(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && newNs.trim() && create.mutate()}
          placeholder="New namespace name..."
          className="flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
        />
        <button
          onClick={() => create.mutate()}
          disabled={!newNs.trim() || create.isPending}
          className="rounded-md bg-violet-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
        >
          Create
        </button>
      </div>

      {create.isError && (
        <p className="mb-3 text-xs text-red-500">
          {create.error instanceof Error ? create.error.message : "Failed to create"}
        </p>
      )}

      <ul className="space-y-1.5">
        {namespaces.map((ns) => (
          <li
            key={ns}
            className="flex items-center justify-between rounded-md border border-slate-100 px-3 py-2 text-sm dark:border-slate-800"
          >
            <button
              onClick={() => selectNamespace(ns)}
              className="font-mono text-xs text-slate-700 hover:text-violet-600 dark:text-slate-300"
            >
              {ns}
            </button>
            <button
              onClick={() => {
                if (confirm(`Delete namespace "${ns}" and ALL its memories?`)) {
                  remove.mutate(ns);
                }
              }}
              className="text-xs text-red-400 hover:text-red-600"
            >
              Delete
            </button>
          </li>
        ))}
        {namespaces.length === 0 && (
          <li className="text-xs text-slate-400">No namespaces yet.</li>
        )}
      </ul>
    </div>
  );
}

function NamespaceStatsPanel({ namespace }: { namespace: string }) {
  const { data } = useQuery({
    queryKey: ["namespace-stats", namespace],
    queryFn: () => fetchNamespaceStats(namespace),
    enabled: !!namespace,
  });

  if (!data) return null;

  return (
    <div className="mt-3 space-y-1 border-t border-slate-100 pt-3 dark:border-slate-800">
      {Object.entries(data).map(([k, v]) => (
        <ConfigRow key={k} label={k} value={typeof v === "object" ? JSON.stringify(v) : String(v)} />
      ))}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
      <h2 className="mb-3 text-sm font-semibold text-slate-600 dark:text-slate-400">{title}</h2>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function StatusRow({ label, url }: { label: string; url: string }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-sm text-slate-700 dark:text-slate-300">{label}</span>
      <a href={url} target="_blank" rel="noreferrer" className="text-xs text-violet-500 hover:underline">
        {url}
      </a>
    </div>
  );
}

function ConfigRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-sm text-slate-700 dark:text-slate-300">{label}</span>
      <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-400">
        {value}
      </span>
    </div>
  );
}
