"use client";

import { useEffect } from "react";
import { useFontSizeStore } from "@/stores/fontSizeStore";

/**
 * Syncs the font-size Zustand store to a CSS class on <html>.
 * Renders nothing — mount once in the root layout.
 */
export function FontSizeClass() {
  const fontSize = useFontSizeStore((s) => s.fontSize);

  useEffect(() => {
    const html = document.documentElement;
    html.classList.remove("font-small", "font-medium", "font-large");
    html.classList.add(`font-${fontSize}`);
  }, [fontSize]);

  return null;
}
