import { useQuery } from "@tanstack/react-query";
import { fetchSubgraph, fetchNeighbors, fetchLineage } from "@/lib/api/graph";

export function useSubgraph(namespace: string) {
  return useQuery({
    queryKey: ["graph", namespace],
    queryFn: () => fetchSubgraph(namespace),
    refetchInterval: 30_000,
    enabled: !!namespace,
  });
}

export function useNeighbors(memoryId: string, depth = 1) {
  return useQuery({
    queryKey: ["neighbors", memoryId, depth],
    queryFn: () => fetchNeighbors(memoryId, depth),
    enabled: !!memoryId,
  });
}

export function useLineage(memoryId: string) {
  return useQuery({
    queryKey: ["lineage", memoryId],
    queryFn: () => fetchLineage(memoryId),
    enabled: !!memoryId,
  });
}
