import { create } from "zustand";
import { persist } from "zustand/middleware";

export type FontSize = "small" | "medium" | "large";

interface FontSizeState {
  fontSize: FontSize;
  setFontSize: (size: FontSize) => void;
}

export const useFontSizeStore = create<FontSizeState>()(
  persist(
    (set) => ({
      fontSize: "medium",
      setFontSize: (size) => set({ fontSize: size }),
    }),
    { name: "dse-font-size" },
  ),
);
