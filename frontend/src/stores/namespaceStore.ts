import { create } from "zustand";

interface NamespaceState {
  namespace: string;
  available: string[];
  setNamespace: (ns: string) => void;
  setAvailable: (list: string[]) => void;
}

export const useNamespaceStore = create<NamespaceState>((set) => ({
  namespace: "",
  available: [],
  setNamespace: (ns) => set({ namespace: ns }),
  setAvailable: (list) =>
    set((state) => ({
      available: list,
      // Auto-select first namespace if none selected yet
      namespace: state.namespace || list[0] || "",
    })),
}));
