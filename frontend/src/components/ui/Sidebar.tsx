"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { fetchNamespaces } from "@/lib/api/namespaces";
import { useNamespaceStore } from "@/stores/namespaceStore";
import { type FontSize, useFontSizeStore } from "@/stores/fontSizeStore";
import { useEffect } from "react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: "Home", tip: "Stats overview for the selected namespace" },
  { href: "/memories", label: "Memories", icon: "Search", tip: "Search and retrieve memories" },
  { href: "/graph", label: "Graph", icon: "Share2", tip: "Interactive knowledge graph visualization" },
  { href: "/conflicts", label: "Conflicts", icon: "AlertTriangle", tip: "Resolve contradictory memory pairs" },
  { href: "/curation", label: "Curation", icon: "Settings", tip: "Browse, edit, compress, and manage memories" },
  { href: "/intelligence", label: "Intelligence", icon: "Zap", tip: "Monitor autonomous memory improvement" },
  { href: "/workflows", label: "Workflows", icon: "Workflow", tip: "Temporal background workflow status" },
  { href: "/settings", label: "Settings", icon: "Cog", tip: "Namespace management and service status" },
];

// Minimal SVG icons to avoid external dependency
const ICONS: Record<string, string> = {
  Home: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1",
  Search: "M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z",
  Share2: "M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z",
  AlertTriangle: "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z",
  Settings: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z",
  Zap: "M13 10V3L4 14h7v7l9-11h-7z",
  Workflow: "M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z",
  Cog: "M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4",
};

function NavIcon({ name }: { name: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-4 w-4"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d={ICONS[name] ?? ICONS.Home} />
    </svg>
  );
}

function NamespaceSelector() {
  const { namespace, available, setNamespace, setAvailable } = useNamespaceStore();

  const { data } = useQuery({
    queryKey: ["namespaces"],
    queryFn: fetchNamespaces,
    refetchInterval: 30_000,
  });

  useEffect(() => {
    if (data && data.length > 0) {
      setAvailable(data);
    }
  }, [data, setAvailable]);

  return (
    <div className="px-3 py-3">
      <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        Namespace
      </label>
      <select
        value={namespace}
        onChange={(e) => setNamespace(e.target.value)}
        className="w-full rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-sm text-slate-700 transition-colors hover:border-violet-300 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-violet-600 dark:focus:border-violet-500"
      >
        {available.length === 0 && (
          <option value="">No namespaces</option>
        )}
        {available.map((ns) => (
          <option key={ns} value={ns}>
            {ns}
          </option>
        ))}
      </select>
    </div>
  );
}

const FONT_SIZES: { value: FontSize; label: string }[] = [
  { value: "small", label: "S" },
  { value: "medium", label: "M" },
  { value: "large", label: "L" },
];

function FontSizeSelector() {
  const { fontSize, setFontSize } = useFontSizeStore();

  return (
    <div>
      <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        Font Size
      </label>
      <div className="flex gap-1">
        {FONT_SIZES.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => setFontSize(value)}
            className={cn(
              "flex-1 rounded-md py-1 text-xs font-medium transition-colors",
              fontSize === value
                ? "bg-violet-100 text-violet-700 dark:bg-violet-900 dark:text-violet-300"
                : "bg-slate-100 text-slate-500 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700",
            )}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-56 flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center gap-2 border-b border-slate-200 px-4 py-4 dark:border-slate-800">
        <span className="text-lg">🧠</span>
        <span className="text-sm font-bold tracking-tight text-violet-600 dark:text-violet-400">
          DSE Dashboard
        </span>
      </div>
      <NamespaceSelector />
      <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
        {NAV_ITEMS.map(({ href, label, icon, tip }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              title={tip}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-violet-50 font-medium text-violet-700 dark:bg-violet-950 dark:text-violet-300"
                  : "text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800",
              )}
            >
              <NavIcon name={icon} />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-slate-200 px-3 py-3 dark:border-slate-800">
        <FontSizeSelector />
        <p className="mt-2 text-[10px] text-slate-400">DSE v0.1.0 — Memory Dashboard</p>
      </div>
    </aside>
  );
}
