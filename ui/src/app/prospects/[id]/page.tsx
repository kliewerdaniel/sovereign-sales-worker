"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useBackend } from "@/components/providers/backend-provider";
import { useAsync } from "@/lib/use-async";
import {
  Badge,
  Hash,
  OutreachBadge,
  TierBadge,
  SectionTitle,
  RefId,
} from "@/components/ui/primitives";
import { fmtTime } from "@/lib/domain";
import type { Tone } from "@/lib/domain";
import { cn } from "@/lib/cn";
import { ArrowLeft, Building2, Mail } from "lucide-react";
import type { Qualification, SalesEvidence, PainPoint, OutreachDraft, PipelineStage } from "@/lib/types";

function bandOf(score: number): { label: string; tone: Tone } {
  if (score >= 60) return { label: "High", tone: "ok" };
  if (score >= 40) return { label: "Medium", tone: "warn" };
  if (score > 0) return { label: "Low", tone: "neutral" };
  return { label: "Insufficient", tone: "bad" };
}

export default function LeadDetailPage() {
  const params = useParams<{ id: string }>();
  const backend = useBackend();
  const { data: lead, loading } = useAsync(() => backend.getLead(params.id), [params.id]);

  if (loading) return <LeadSkeleton />;
  if (!lead) return <LeadNotFound id={params.id} />;

  const band = bandOf(lead.score);
  const qual = lead.qualifications[0];
  const ev: SalesEvidence[] = lead.evidence ?? [];
  const pains: PainPoint[] = lead.pain_points ?? [];
  const drafts: OutreachDraft[] = lead.drafts ?? [];

  return (
    <div className="mx-auto max-w-7xl px-5 py-5">
      <Link href="/prospects" className="inline-flex items-center gap-1 text-xs text-ink-3 hover:text-ink-1">
        <ArrowLeft className="h-3.5 w-3.5" /> Prospects
      </Link>

      <div className="surface mt-3 px-5 py-4">
        <div className="flex flex-wrap items-start gap-4">
          <div className="text-center">
            <div className="text-3xl font-semibold tabular-nums text-ink-0">{lead.score.toFixed(1)}</div>
            <Badge tone={band.tone} className="mt-1">{band.label}</Badge>
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="text-lg font-semibold text-ink-0">{lead.company_name ?? lead.id}</span>
              <Badge tone="ok">{lead.stage.replace(/_/g, " ")}</Badge>
              <Badge tone="neutral">{lead.owner}</Badge>
              <Hash value={lead.id} />
            </div>
            <p className="mt-1.5 text-sm text-ink-3">{lead.industry}</p>
            {lead.next_action ? (
              <p className="mt-2 text-[13px] text-ink-2">
                <span className="text-ink-3">Next: </span>
                {lead.next_action}
              </p>
            ) : null}
          </div>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,360px)]">
        <div className="space-y-5">
          {qual ? <QualificationPanel q={qual} /> : null}

          <div>
            <SectionTitle hint={`${pains.length} found`}>Pain points</SectionTitle>
            {pains.length === 0 ? (
              <div className="surface px-4 py-6 text-center text-sm text-ink-3">No pain points recorded.</div>
            ) : (
              <div className="space-y-2.5">
                {pains.map((p) => (
                  <div key={p.id} className="surface px-4 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm text-ink-1">{p.text}</p>
                      <Badge tone={p.opportunity_score >= 80 ? "ok" : p.opportunity_score >= 50 ? "warn" : "neutral"}>
                        opp {p.opportunity_score}
                      </Badge>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5 text-[10px]">
                      <span className="mono rounded border border-hairline-soft bg-surface-3/40 px-1.5 py-0.5 text-ink-2">sev {p.severity}</span>
                      <span className="mono rounded border border-hairline-soft bg-surface-3/40 px-1.5 py-0.5 text-ink-2">freq {p.frequency}</span>
                      <span className="mono rounded border border-hairline-soft bg-surface-3/40 px-1.5 py-0.5 text-ink-2">rev {p.revenue_impact}</span>
                      <span className="mono rounded border border-hairline-soft bg-surface-3/40 px-1.5 py-0.5 text-ink-2">auto {p.automation_potential}</span>
                      <span className="mono rounded border border-hairline-soft bg-surface-3/40 px-1.5 py-0.5 text-ink-2">diff {p.implementation_difficulty}</span>
                    </div>
                    <div className="mt-2"><TierBadge tier={p.tier} /></div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <SectionTitle hint={`${drafts.length} draft(s)`}>Outreach</SectionTitle>
            {drafts.length === 0 ? (
              <div className="surface px-4 py-6 text-center text-sm text-ink-3">No outreach drafts.</div>
            ) : (
              <div className="space-y-2.5">
                {drafts.map((d) => (
                  <div key={d.id} className="surface px-4 py-3">
                    <div className="flex items-center gap-2">
                      <OutreachBadge s={d.state} />
                      <span className="text-sm font-medium text-ink-0">{d.subject}</span>
                      <span className="mono text-[11px] text-ink-3">{d.channel}</span>
                    </div>
                    <pre className="mt-2 whitespace-pre-wrap rounded-md border border-hairline-soft bg-surface-0 p-3 text-[12px] leading-relaxed text-ink-2">{d.body}</pre>
                    <div className="mt-2 flex items-center gap-1.5 text-[11px] text-ink-3">
                      evidence
                      {d.evidence_ids.map((e) => <RefId key={e} value={e} />)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-5">
          <div>
            <SectionTitle hint={`${ev.length} records`}>Evidence</SectionTitle>
            {ev.length === 0 ? (
              <div className="surface px-4 py-6 text-center text-sm text-ink-3">No evidence yet.</div>
            ) : (
              <div className="space-y-2.5">
                {ev.map((e) => (
                  <div key={e.id} className="surface px-4 py-3">
                    <div className="flex items-center gap-2">
                      <TierBadge tier={e.tier} />
                      <span className="text-[11px] text-ink-3">{e.claim_type}</span>
                      <span className="ml-auto text-[11px] text-ink-3">{fmtTime(e.created)}</span>
                    </div>
                    <p className="mt-1.5 text-[13px] text-ink-1">{e.claim_text}</p>
                    <p className="mt-1 border-l-2 border-hairline-soft pl-2 text-[12px] italic text-ink-3">“{e.excerpt}”</p>
                    <div className="mt-2 font-mono text-[10px] text-ink-4">{e.source_ref}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {lead.company ? (
            <div>
              <SectionTitle hint="firmographic">Company</SectionTitle>
              <div className="surface px-4 py-3.5 text-sm">
                <div className="flex items-center gap-2 text-ink-0">
                  <Building2 className="h-4 w-4 text-ink-3" /> {lead.company.name}
                </div>
                <dl className="mt-2 space-y-1 text-[12px] text-ink-3">
                  <Row k="Domain" v={lead.company.domain} />
                  <Row k="Industry" v={lead.company.industry} />
                  <Row k="Geography" v={lead.company.geography} />
                  <Row k="Team size" v={String(lead.company.team_size)} />
                </dl>
              </div>
            </div>
          ) : null}

          {lead.contacts && lead.contacts.length > 0 ? (
            <div>
              <SectionTitle hint={`${lead.contacts.length}`}>Contacts</SectionTitle>
              <div className="space-y-2">
                {lead.contacts.map((c) => (
                  <div key={c.id} className="surface px-4 py-3 text-sm">
                    <div className="flex items-center gap-2">
                      <span className="text-ink-0">{c.name}</span>
                      {c.is_decision_maker ? <Badge tone="accent">decision-maker</Badge> : null}
                    </div>
                    <div className="mt-1 flex items-center gap-1.5 text-[12px] text-ink-3">
                      <Mail className="h-3.5 w-3.5" /> {c.email}
                    </div>
                    <div className="text-[12px] text-ink-3">{c.role}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function QualificationPanel({ q }: { q: Qualification }) {
  const SUB: Array<{ key: keyof Qualification; label: string }> = [
    { key: "icp_fit", label: "ICP fit" },
    { key: "pain_signal", label: "Pain" },
    { key: "urgency", label: "Urgency" },
    { key: "economic_potential", label: "Econ." },
    { key: "accessibility", label: "Access" },
    { key: "confidence", label: "Conf." },
  ];
  return (
    <div>
      <SectionTitle hint={`v${q.version} · ${q.model}`}>Qualification breakdown</SectionTitle>
      <div className="surface p-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {SUB.map(({ key, label }) => {
            const v = q[key] as number;
            return (
              <div key={label} className="rounded-md border border-hairline-soft bg-surface-1 p-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-ink-3">{label}</span>
                  <span className="mono text-sm font-semibold text-ink-0">{v}</span>
                </div>
                <div className="mt-1.5 h-1.5 rounded-full bg-surface-3">
                  <div className={cn("h-full rounded-full", toneBar(v))} style={{ width: `${v}%` }} />
                </div>
              </div>
            );
          })}
        </div>
        <p className="mt-3 border-t border-hairline-soft pt-3 text-[13px] leading-relaxed text-ink-2">{q.reasoning}</p>
        <div className="mt-2 flex items-center gap-1.5 text-[11px] text-ink-3">
          evidence
          {q.evidence_ids.map((e) => <RefId key={e} value={e} />)}
        </div>
      </div>
    </div>
  );
}

function toneBar(v: number): string {
  if (v >= 60) return "bg-ok";
  if (v >= 40) return "bg-warn";
  return "bg-ink-3";
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-ink-4">{k}</dt>
      <dd className="text-ink-1">{v}</dd>
    </div>
  );
}

function LeadSkeleton() {
  return (
    <div className="mx-auto max-w-7xl px-5 py-5">
      <div className="surface h-32 animate-pulse" />
      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-[1fr_360px]">
        <div className="surface h-96 animate-pulse" />
        <div className="surface h-96 animate-pulse" />
      </div>
    </div>
  );
}

function LeadNotFound({ id }: { id: string }) {
  return (
    <div className="mx-auto max-w-3xl px-5 py-16">
      <div className="surface px-6 py-12 text-center">
        <div className="text-lg font-medium text-ink-0">Prospect not found</div>
        <p className="mono mt-3 text-xs text-ink-4">{id}</p>
      </div>
    </div>
  );
}
