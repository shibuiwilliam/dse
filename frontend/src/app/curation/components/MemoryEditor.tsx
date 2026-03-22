"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Memory } from "@/lib/types";

interface Props {
  memory: Memory;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MemoryEditor({ memory, open, onOpenChange }: Props) {
  const qc = useQueryClient();
  const [summary, setSummary] = useState(memory.summary);
  const [importance, setImportance] = useState(memory.importance_score);
  const [tags, setTags] = useState(memory.tags.join(", "));

  const update = useMutation({
    mutationFn: () =>
      api.put(`/v1/memories/${memory.id}`, {
        summary,
        importance_score: importance,
        tags: tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["curation-memories"] });
      onOpenChange(false);
    },
  });

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-xl border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-700 dark:bg-slate-900">
          <Dialog.Title className="mb-4 text-lg font-semibold">Edit Memory</Dialog.Title>
          <Dialog.Description className="mb-4 text-xs text-slate-500">
            {memory.id} — {memory.memory_type}
          </Dialog.Description>

          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Summary</label>
              <textarea
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                rows={3}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">
                Importance ({(importance * 100).toFixed(0)}%)
              </label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={importance}
                onChange={(e) => setImportance(Number(e.target.value))}
                className="w-full"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">
                Tags (comma-separated)
              </label>
              <input
                type="text"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
              />
            </div>
          </div>

          <div className="mt-6 flex justify-end gap-2">
            <Dialog.Close asChild>
              <button className="rounded-md px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800">
                Cancel
              </button>
            </Dialog.Close>
            <button
              onClick={() => update.mutate()}
              disabled={update.isPending}
              className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
            >
              {update.isPending ? "Saving..." : "Save"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
