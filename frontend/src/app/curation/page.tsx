"use client";

import * as Tabs from "@radix-ui/react-tabs";
import { useNamespaceStore } from "@/stores/namespaceStore";
import { InfoTip } from "@/components/ui/Tooltip";
import { CompressionPanel } from "./components/CompressionPanel";
import { ImportanceChart } from "./components/ImportanceChart";
import { MemoryBrowser } from "./components/MemoryBrowser";
import { ProspectiveList } from "./components/ProspectiveList";

export default function CurationPage() {
  const namespace = useNamespaceStore((s) => s.namespace);

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          Memory Curation
          <InfoTip text="Browse, edit, pin, and archive memories. Trigger semantic compression, manage prospective reminders, and view analytics." />
        </h1>
      </div>

      <Tabs.Root defaultValue="browse">
        <Tabs.List className="mb-6 flex gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-800">
          {[
            { value: "browse", label: "Memories", tip: "Browse, filter, edit, pin, or forget memories" },
            { value: "compression", label: "Compression", tip: "Trigger semantic compression to distill episodic clusters into knowledge" },
            { value: "prospective", label: "Prospective", tip: "Manage future reminders and condition-based triggers" },
            { value: "analytics", label: "Analytics", tip: "Charts for memory type and decay distribution" },
          ].map(({ value, label, tip }) => (
            <Tabs.Trigger
              key={value}
              value={value}
              title={tip}
              className="flex-1 rounded-md px-3 py-1.5 text-sm font-medium text-slate-500 transition-colors data-[state=active]:bg-white data-[state=active]:text-slate-900 data-[state=active]:shadow-sm dark:text-slate-400 dark:data-[state=active]:bg-slate-700 dark:data-[state=active]:text-slate-100"
            >
              {label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="browse">
          <MemoryBrowser namespace={namespace} />
        </Tabs.Content>
        <Tabs.Content value="compression">
          <CompressionPanel namespace={namespace} />
        </Tabs.Content>
        <Tabs.Content value="prospective">
          <ProspectiveList namespace={namespace} />
        </Tabs.Content>
        <Tabs.Content value="analytics">
          <ImportanceChart namespace={namespace} />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}
