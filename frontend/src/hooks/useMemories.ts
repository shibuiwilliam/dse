import { useQuery } from "@tanstack/react-query";
import { fetchCurationMemories, fetchCurationStats } from "@/lib/api/curation";

export function useMemories(namespace: string, memoryType = "all", sortBy = "importance") {
  return useQuery({
    queryKey: ["curation-memories", namespace, memoryType, sortBy],
    queryFn: () => fetchCurationMemories({ namespace, memoryType, sortBy }),
    enabled: !!namespace,
  });
}

export function useStats(namespace: string) {
  return useQuery({
    queryKey: ["curation-stats", namespace],
    queryFn: () => fetchCurationStats(namespace),
    enabled: !!namespace,
  });
}
