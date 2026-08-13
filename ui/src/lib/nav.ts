import {
  Activity,
  Boxes,
  FileText,
  ScrollText,
  Gauge,
  GitBranch,
  Hammer,
  LayoutDashboard,
  ListChecks,
  PlayCircle,
  ShieldCheck,
  Sparkles,
  Users,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  desc: string;
}

export const NAV: NavItem[] = [
  { href: "/", label: "Mission Control", icon: LayoutDashboard, desc: "What is happening right now" },
  { href: "/runs", label: "Runs", icon: Gauge, desc: "Every worker execution" },
  { href: "/workers", label: "Workers", icon: Boxes, desc: "Worker identities & config" },
  { href: "/prospects", label: "Prospects", icon: Users, desc: "Sales pipeline & qualification" },
  { href: "/evidence", label: "Evidence", icon: FileText, desc: "The provenance database" },
  { href: "/artifacts", label: "Artifacts", icon: Sparkles, desc: "Outputs of computation" },
  { href: "/approvals", label: "Approvals", icon: ListChecks, desc: "Human-in-the-loop gate" },
  { href: "/policy", label: "Policy", icon: ShieldCheck, desc: "What the worker may do" },
  { href: "/tools", label: "Tools", icon: Hammer, desc: "Tool registry & calls" },
  { href: "/audit", label: "Audit", icon: ScrollText, desc: "Hash-chained trail" },
  { href: "/replay", label: "Replay", icon: PlayCircle, desc: "Reconstruct a run" },
  { href: "/settings", label: "Settings", icon: GitBranch, desc: "Backend & appearance" },
];

export function navLabel(path: string): string {
  return NAV.find((n) => n.href === path)?.label ?? "Sovereign Worker";
}
