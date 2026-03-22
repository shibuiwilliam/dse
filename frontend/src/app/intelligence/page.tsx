"use client";

import { useNamespaceStore } from "@/stores/namespaceStore";
import { InfoTip } from "@/components/ui/Tooltip";
import { CompressionHistory } from "./components/CompressionHistory";
import { DiscoveryLog } from "./components/DiscoveryLog";
import { ImportanceHeatmap } from "./components/ImportanceHeatmap";

export default function IntelligencePage() {
  const namespace = useNamespaceStore((s) => s.namespace);

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          Intelligence Monitor
          <InfoTip text="Monitor autonomous memory improvement: importance scoring distribution, semantic compression results, and auto-discovered relationships." />
        </h1>
      </div>

      <div className="space-y-6">
        <ImportanceHeatmap namespace={namespace} />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <CompressionHistory namespace={namespace} />
          <DiscoveryLog namespace={namespace} />
        </div>
      </div>
    </div>
  );
}
