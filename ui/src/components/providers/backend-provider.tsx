"use client";

import { createContext, useContext } from "react";
import { demoBackend, type Backend } from "@/lib/api";

const Ctx = createContext<Backend>(demoBackend);

export function BackendProvider({
  children,
  backend,
}: {
  children: React.ReactNode;
  backend?: Backend;
}) {
  return <Ctx.Provider value={backend ?? demoBackend}>{children}</Ctx.Provider>;
}

export function useBackend(): Backend {
  return useContext(Ctx);
}
