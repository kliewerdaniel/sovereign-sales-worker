"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { navLabel } from "@/lib/nav";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // pick the most specific nav label for the current section
  const section = `/${pathname.split("/").filter(Boolean)[0] ?? ""}`;
  const title = navLabel(section === "/" ? "/" : section);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar title={title} />
        <main className="app-backdrop flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
