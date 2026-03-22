import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchConflicts, resolveConflict } from "@/lib/api/conflicts";

export function useConflicts(namespace: string) {
  return useQuery({
    queryKey: ["conflicts", namespace],
    queryFn: () => fetchConflicts(namespace),
    refetchInterval: 10_000,
    enabled: !!namespace,
  });
}

export function useResolveConflict(namespace: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ idA, idB, keep }: { idA: string; idB: string; keep: "A" | "B" | "both" }) =>
      resolveConflict(namespace, idA, idB, keep),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["conflicts"] }),
  });
}
