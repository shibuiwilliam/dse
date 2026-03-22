import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Providers } from "./providers";
import { Sidebar } from "@/components/ui/Sidebar";
import { FontSizeClass } from "@/components/ui/FontSizeClass";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "DSE — Memory Dashboard",
  description: "Dynamic Search Engine for Agentic Memory",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ja" className="font-medium">
      <body className="bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
        <Providers>
          <FontSizeClass />
          <div className="flex h-screen">
            <Sidebar />
            <main className="flex-1 overflow-auto">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
