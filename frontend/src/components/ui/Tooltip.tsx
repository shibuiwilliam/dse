"use client";

import { type ReactNode, useState } from "react";

interface TooltipProps {
  text: string;
  children: ReactNode;
  position?: "top" | "bottom" | "left" | "right";
}

/**
 * Lightweight tooltip — wraps any element and shows a tooltip on hover.
 * No external dependency required.
 */
export function Tooltip({ text, children, position = "top" }: TooltipProps) {
  const [show, setShow] = useState(false);

  const positionClasses: Record<string, string> = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left: "right-full top-1/2 -translate-y-1/2 mr-2",
    right: "left-full top-1/2 -translate-y-1/2 ml-2",
  };

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <span
          role="tooltip"
          className={`pointer-events-none absolute z-50 max-w-xs whitespace-normal rounded-md bg-slate-800 px-2.5 py-1.5 text-xs leading-snug text-slate-100 shadow-lg dark:bg-slate-700 ${positionClasses[position]}`}
        >
          {text}
        </span>
      )}
    </span>
  );
}

/**
 * Small "?" info icon that shows a tooltip on hover.
 * Use next to headings and labels.
 */
export function InfoTip({ text, position = "top" }: { text: string; position?: TooltipProps["position"] }) {
  return (
    <Tooltip text={text} position={position}>
      <span className="inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full bg-slate-200 text-[10px] font-bold text-slate-500 dark:bg-slate-700 dark:text-slate-400">
        ?
      </span>
    </Tooltip>
  );
}
