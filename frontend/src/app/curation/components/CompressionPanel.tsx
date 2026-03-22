"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { triggerCompression } from "@/lib/api/curation";
import { InfoTip } from "@/components/ui/Tooltip";

export function CompressionPanel({ namespace }: { namespace: string }) {
  const [days, setDays] = useState(30);

  const compress = useMutation({
    mutationFn: () => triggerCompression(namespace, days),
  });

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
          Semantic Compression
          <InfoTip text="Clusters similar episodic memories using HDBSCAN, then uses LLM to generalize each cluster into a single semantic memory." />
        </h3>
        <p className="mb-4 text-sm text-slate-500">
          Cluster similar episodic memories using HDBSCAN and distill them into generalized semantic
          knowledge via LLM.
        </p>
        <div className="flex items-center gap-3">
          <label className="text-sm text-slate-600">Lookback days:</label>
          <input
            type="number"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            min={1}
            max={365}
            className="w-20 rounded-md border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
          />
          <button
            onClick={() => compress.mutate()}
            disabled={compress.isPending}
            className="rounded-md bg-violet-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
          >
            {compress.isPending ? "Running..." : "Run Compression"}
          </button>
        </div>
        {compress.isSuccess && (
          <p className="mt-3 text-sm text-emerald-600">Compression triggered successfully.</p>
        )}
        {compress.isError && (
          <p className="mt-3 text-sm text-red-600">
            Error: {compress.error instanceof Error ? compress.error.message : "Unknown"}
          </p>
        )}
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <h3 className="mb-2 text-sm font-semibold">How it works</h3>
        <ol className="space-y-1.5 text-sm text-slate-500">
          <li>1. Fetch episodic memories from the last {days} days</li>
          <li>2. Generate embeddings and cluster with HDBSCAN</li>
          <li>3. Skip clusters below min confidence ({">"}0.70)</li>
          <li>4. Check for existing similar semantic memories (idempotency)</li>
          <li>5. LLM generalizes each cluster into semantic knowledge</li>
          <li>6. Create DERIVES edges from semantic to source episodes</li>
          <li>7. Decay source episode importance by 50%</li>
        </ol>
      </div>
    </div>
  );
}
