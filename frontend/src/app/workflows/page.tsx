"use client";

import { InfoTip } from "@/components/ui/Tooltip";

export default function WorkflowsPage() {
  return (
    <div className="p-6">
      <h1 className="mb-6 flex items-center gap-2 text-2xl font-semibold">
        Temporal Workflows
        <InfoTip text="Background workflows orchestrated by Temporal. These run automatically on schedules or are triggered by memory operations." />
      </h1>
      <div className="rounded-lg border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
          Monitor and manage Temporal workflows that power DSE{"'"}s background processing.
        </p>
        <div className="space-y-3">
          {[
            { name: "MemoryWriteWorkflow", queue: "dse-main", desc: "Saga-pattern memory persistence (Storage → Embedding → Index → Graph → Provenance → Contradiction Check)" },
            { name: "ContradictionCheckWorkflow", queue: "dse-main", desc: "3-level contradiction detection and resolution" },
            { name: "ProspectiveScanWorkflow", queue: "dse-main", desc: "Every-minute scan for prospective memory triggers" },
            { name: "SemanticCompressionWorkflow", queue: "dse-maintenance", desc: "Weekly HDBSCAN clustering + LLM generalization" },
            { name: "DailyMaintenanceWorkflow", queue: "dse-maintenance", desc: "Decay score updates and archiving" },
            { name: "RelationDiscoveryWorkflow", queue: "dse-discovery", desc: "Daily ANN + LLM relation classification" },
            { name: "TemporalEdgeBuildWorkflow", queue: "dse-discovery", desc: "Daily Allen's Interval Algebra edge creation" },
          ].map((w) => (
            <div
              key={w.name}
              className="flex items-start gap-3 rounded-md border border-slate-100 p-3 dark:border-slate-800"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
                  {w.name}
                </p>
                <p className="mt-0.5 text-xs text-slate-500">{w.desc}</p>
              </div>
              <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                {w.queue}
              </span>
            </div>
          ))}
        </div>
        <p className="mt-6 text-xs text-slate-400">
          Open <a href="http://localhost:8080" target="_blank" rel="noreferrer" className="text-violet-500 underline">Temporal UI</a> for live workflow execution details.
        </p>
      </div>
    </div>
  );
}
