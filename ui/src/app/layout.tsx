import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/providers/theme-provider";
import { BackendProvider } from "@/components/providers/backend-provider";
import { CommandPaletteProvider } from "@/components/providers/command-palette-provider";
import { AppShell } from "@/components/layout/app-shell";
import { DemoNotice } from "@/components/layout/demo-notice";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jet", display: "swap" });

export const metadata: Metadata = {
  title: "Sovereign Worker — Control Plane",
  description:
    "Policy-controlled autonomous workers. Inspectable, evidence-driven, under human control.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`} suppressHydrationWarning>
      <body>
        <ThemeProvider>
          <BackendProvider>
            <CommandPaletteProvider>
              <AppShell>
                <DemoNotice />
                {children}
              </AppShell>
            </CommandPaletteProvider>
          </BackendProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
