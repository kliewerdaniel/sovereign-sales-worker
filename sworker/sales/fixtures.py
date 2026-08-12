"""Consulting prospect fixtures for the Sovereign Sales Worker.

A realistic, self-contained demo dataset so ``sworker sales daily-run`` produces
*researched and qualified* leads out of the box — and so the score differentiation
is meaningful (each company carries its own local knowledge doc, which the
research tool reads in a scoped, per-lead fashion).

Every company is described only with signal/pain phrases the research engine
actually recognises (see ``research.py`` SIGNALS / PAIN_PATTERNS): team size,
tooling, urgency, budget, a published contact, and documented pain (manual
re-entry, tribal knowledge, hand-assembled documents, SaaS sprawl, coverage
gaps, no measurement). No live data, no fabrication.

The doc for each company is written to ``company/<domain-stem>.md`` by
``sworker sales seed``; the research tool resolves that file per lead so one
company's evidence never leaks into another's score.
"""

from __future__ import annotations

from typing import Dict, List

# (name, website, industry, geography, team_size, contact_name, contact_role,
#  contact_email, notes, knowledge_doc)
_FIXTURE_FIELDS = (
    "name", "website", "industry", "geography", "team_size",
    "contact_name", "contact_role", "contact_email", "notes", "doc",
)

# 12 consulting prospects spread across the 7 ICP-ranked industries, with varied
# team sizes, pain intensity, and signal density so the qualification score
# separates them rather than collapsing to a flat band.
COMPANIES: List[Dict[str, str]] = [
    {
        "name": "Brightpath Consulting",
        "website": "https://brightpath.example",
        "industry": "Professional Services",
        "geography": "Austin, TX",
        "team_size": "65",
        "contact_name": "Dana Okafor",
        "contact_role": "Operations Lead",
        "contact_email": "ops@brightpath.example",
        "notes": "65-person consultancy; SaaS sprawl + reporting burden.",
        "doc": (
            "# Brightpath Consulting — Company Knowledge\n\n"
            "65 employees across three practice areas. We run client engagements "
            "on a patchwork of HubSpot, Notion, Slack, and a dozen spreadsheets "
            "that nobody owns.\n\n"
            "Client proposals are assembled by hand from last quarter's deck. The "
            "same client data gets re-entered into three different systems because "
            "no single source of truth exists. Our weekly report is rebuilt by hand "
            "every week and nobody reads half of it.\n\n"
            "After the Q3 cost review, leadership wants to cut SaaS spend. We "
            "evaluated a $12,000 monthly tool consolidation but have no visibility "
            "into what we actually use.\n\n"
            "Contact: ops@brightpath.example\n"
        ),
    },
    {
        "name": "Lumen Capital Advisors",
        "website": "https://lumen-capital.example",
        "industry": "Professional Services",
        "geography": "Boston, MA",
        "team_size": "38",
        "contact_name": "Priya Raman",
        "contact_role": "Managing Partner",
        "contact_email": "priya@lumen-capital.example",
        "notes": "38-person advisory; client-data privacy + reporting burden.",
        "doc": (
            "# Lumen Capital Advisors — Company Knowledge\n\n"
            "38 employees advising family offices. Client reporting is put together "
            "by hand for every quarterly cycle and the same numbers are re-keyed "
            "into our CRM, our billing system, and a board deck.\n\n"
            "Critical context lives in one partner's head; when she is out, no one "
            "can find the source model. We are hiring two analysts but they will "
            "just absorb the manual entry.\n\n"
            "After a client data leak at a competitor, privacy is the buying "
            "trigger. We budgeted $9,500 for a local-first knowledge system before "
            "end of quarter.\n\n"
            "Contact: priya@lumen-capital.example\n"
        ),
    },
    {
        "name": "Granite Ops Group",
        "website": "https://granite-ops.example",
        "industry": "Internal Ops / RevOps",
        "geography": "Chicago, IL",
        "team_size": "150",
        "contact_name": "Marcus Webb",
        "contact_role": "Head of RevOps",
        "contact_email": "marcus@granite-ops.example",
        "notes": "150-person internal ops team; repetitive reporting + onboarding.",
        "doc": (
            "# Granite Ops Group — Company Knowledge\n\n"
            "150-person internal operations team owning reporting, onboarding, and "
            "internal tooling for a larger parent org. We don't track how many "
            "hours go into the monthly operating review.\n\n"
            "The same operational data is copied over between our warehouse, "
            "Salesforce, and a reporting workbook. Tribal knowledge about the "
            "onboarding runbook lives in one manager's head.\n\n"
            "We are now hiring two ops analysts and paying for overlapping SaaS "
            "tools to do what one owned workflow system could. Cost review lands "
            "this quarter; we set aside $18,000 for automation.\n\n"
            "Contact: marcus@granite-ops.example\n"
        ),
    },
    {
        "name": "Vertex Logistics",
        "website": "https://vertex-logistics.example",
        "industry": "SaaS-Dependent SMBs",
        "geography": "Denver, CO",
        "team_size": "95",
        "contact_name": "Sofia Marin",
        "contact_role": "COO",
        "contact_email": "sofia@vertex-logistics.example",
        "notes": "95-person 3PL; paying for too many overlapping SaaS tools.",
        "doc": (
            "# Vertex Logistics — Company Knowledge\n\n"
            "95 employees running third-party logistics. We carry too many SaaS "
            "tools — TMS, WMS, billing, and a custom Airtable — that overlap and "
            "none of them talk to each other.\n\n"
            "Shipment exceptions are tracked manually and re-entered into the "
            "customer portal by hand. After hours, no one covers the exception "
            "queue and SLAs slip.\n\n"
            "Leadership wants to cut software spend; we pay roughly $14,000 a month "
            "across subscriptions and can't measure the ROI of any of them. A "
            "local-first consolidation is on the table for next quarter.\n\n"
            "Contact: sofia@vertex-logistics.example\n"
        ),
    },
    {
        "name": "Meridian Law Group",
        "website": "https://meridian-law.example",
        "industry": "Law & Accounting",
        "geography": "Seattle, WA",
        "team_size": "45",
        "contact_name": "Ellen Cho",
        "contact_role": "Managing Partner",
        "contact_email": "ellen@meridian-law.example",
        "notes": "45-person firm; document-heavy, privacy-critical.",
        "doc": (
            "# Meridian Law Group — Company Knowledge\n\n"
            "Document-heavy law practice with 45 employees. Contracts are assembled "
            "by hand from templates and client matter knowledge lives in one "
            "partner's head.\n\n"
            "The same client intake details are re-entered into our case system, "
            "our billing system, and a shared spreadsheet. We don't track how long "
            "intake actually takes.\n\n"
            "Buying intent: evaluating local-first document automation after a Q3 "
            "cost review of SaaS spend. Privacy is non-negotiable; we will not put "
            "client data in a cloud AI. Budget discussed around $7,500.\n\n"
            "Contact: ellen@meridian-law.example\n"
        ),
    },
    {
        "name": "Ridgeway Family Law",
        "website": "https://ridgeway-law.example",
        "industry": "Law & Accounting",
        "geography": "Portland, OR",
        "team_size": "28",
        "contact_name": "Tom Ridgeway",
        "contact_role": "Founder",
        "contact_email": "tom@ridgeway-law.example",
        "notes": "28-person firm; document assembly by hand, privacy-sensitive.",
        "doc": (
            "# Ridgeway Family Law — Company Knowledge\n\n"
            "28-employee family law firm. Pleadings and settlement packets are put "
            "together by hand and the same facts are typed into three systems.\n\n"
            "Firm knowledge is scattered between two partners; when one is out, "
            "cases stall. We have no visibility into how many matters are actually "
            "profitable.\n\n"
            "We are hiring a paralegal but want to reduce manual entry first. A "
            "local-first knowledge assistant is the goal; we will not use cloud AI "
            "on client files. Set aside about $6,000.\n\n"
            "Contact: tom@ridgeway-law.example\n"
        ),
    },
    {
        "name": "Harborview Clinic",
        "website": "https://harborview-clinic.example",
        "industry": "Healthcare & Clinics",
        "geography": "San Diego, CA",
        "team_size": "80",
        "contact_name": "Dr. Aisha Bello",
        "contact_role": "Practice Administrator",
        "contact_email": "aisha@harborview-clinic.example",
        "notes": "80-person clinic; scheduling/billing ops, HIPAA-adjacent privacy.",
        "doc": (
            "# Harborview Clinic — Company Knowledge\n\n"
            "80-employee multispecialty clinic. Scheduling and billing ops run on a "
            "mix of practice-management software, Excel, and a lot of manual entry.\n\n"
            "Patient intake data is re-keyed from the phone system into the EHR and "
            "again into billing. On weekends no one covers the referral queue and "
            "appointments slip.\n\n"
            "Privacy (HIPAA-adjacent) makes local-first a differentiator; we will "
            "not send patient data to a cloud vendor. We budgeted $11,000 for an "
            "internal automation that does not leave the machine.\n\n"
            "Contact: aisha@harborview-clinic.example\n"
        ),
    },
    {
        "name": "Northwind Manufacturing",
        "website": "https://northwind-mfg.example",
        "industry": "Manufacturing & Trades",
        "geography": "Cleveland, OH",
        "team_size": "120",
        "contact_name": "Greg Halloran",
        "contact_role": "Plant Manager",
        "contact_email": "greg@northwind-mfg.example",
        "notes": "120-person manufacturer; quoting + tribal knowledge ops.",
        "doc": (
            "# Northwind Manufacturing — Company Knowledge\n\n"
            "120-employee SMB manufacturer. Quotes are built by hand from the "
            "salesperson's memory and the same specs are re-entered into the ERP "
            "and the job traveler.\n\n"
            "Quoting knowledge is tribal — it lives in two senior estimators' "
            "heads. When they are out, quotes stall. We don't track win rates by "
            "product line.\n\n"
            "We are evaluating local-first document and knowledge automation after "
            "a cost review; set aside roughly $10,000. No cloud AI on process data.\n\n"
            "Contact: greg@northwind-mfg.example\n"
        ),
    },
    {
        "name": "Forge Metalworks",
        "website": "https://forge-metalworks.example",
        "industry": "Manufacturing & Trades",
        "geography": "Pittsburgh, PA",
        "team_size": "175",
        "contact_name": "Lena Petrov",
        "contact_role": "VP Operations",
        "contact_email": "lena@forge-metalworks.example",
        "notes": "175-person fabricator; quoting tribal knowledge, SaaS sprawl.",
        "doc": (
            "# Forge Metalworks — Company Knowledge\n\n"
            "175-employee metal fabricator. Job quotes are assembled by hand and the "
            "same bill of materials is copied over between CAD, the ERP, and the "
            "shop floor tablet.\n\n"
            "Estimating know-how is scattered across three senior leads; no single "
            "searchable source exists. We carry overlapping SaaS for quoting, "
            "scheduling, and QA that barely integrate.\n\n"
            "Leadership wants to cut software spend this quarter and has $16,000 "
            "earmarked for an owned workflow system. After hours, the RFQ queue is "
            "unattended.\n\n"
            "Contact: lena@forge-metalworks.example\n"
        ),
    },
    {
        "name": "Atlas SaaS Co",
        "website": "https://atlas-saas.example",
        "industry": "SaaS-Dependent SMBs",
        "geography": "Remote / SF",
        "team_size": "60",
        "contact_name": "Jon Park",
        "contact_role": "CEO",
        "contact_email": "jon@atlas-saas.example",
        "notes": "60-person SaaS vendor; many subscriptions, ROI pressure.",
        "doc": (
            "# Atlas SaaS Co — Company Knowledge\n\n"
            "60-employee B2B SaaS company. Ironically we run too many SaaS tools "
            "ourselves — Intercom, Zendesk, HubSpot, Notion, Airtable, plus a "
            "sprawl of smaller subscriptions.\n\n"
            "Customer context is re-entered by hand from Zendesk into our CRM and "
            "our success playbooks. Reporting takes a full day each month and "
            "nobody reads the deck.\n\n"
            "We are doing a cost review and want to show ROI on the stack before "
            "renewals; budget around $8,000 for internal automation. Local-first "
            "appeals because we handle customer data.\n\n"
            "Contact: jon@atlas-saas.example\n"
        ),
    },
    {
        "name": "Cedar & Stone Architects",
        "website": "https://cedar-stone.example",
        "industry": "Agencies & Content Studios",
        "geography": "Boulder, CO",
        "team_size": "22",
        "contact_name": "Mara Lindqvist",
        "contact_role": "Principal",
        "contact_email": "mara@cedar-stone.example",
        "notes": "22-person architecture studio; proposals by hand, client reporting.",
        "doc": (
            "# Cedar & Stone Architects — Company Knowledge\n\n"
            "22-employee architecture studio. Proposals are put together by hand "
            "for every RFP and the same project history is re-keyed into our PM tool "
            "and our accounting system.\n\n"
            "We produce a client report every month that takes a day and nobody "
            "reads. Studio knowledge is scattered across senior architects' drives.\n\n"
            "We would like a local-first assistant to assemble proposals and keep "
            "project knowledge searchable. Budget discussed near $5,500.\n\n"
            "Contact: mara@cedar-stone.example\n"
        ),
    },
    {
        "name": "Saffron Marketing Studio",
        "website": "https://saffron-studio.example",
        "industry": "Agencies & Content Studios",
        "geography": "Nashville, TN",
        "team_size": "18",
        "contact_name": "Bea Nguyen",
        "contact_role": "Studio Director",
        "contact_email": "bea@saffron-studio.example",
        "notes": "18-person content studio; creative ops bottlenecks, SaaS sprawl.",
        "doc": (
            "# Saffron Marketing Studio — Company Knowledge\n\n"
            "18-person content studio. Client briefs are re-entered by hand from "
            "email into our project tool, Notion, and the client portal.\n\n"
            "We carry overlapping SaaS for social, email, and analytics that do not "
            "talk to each other. The weekly content report is built by hand and "
            "often slips past Friday.\n\n"
            "We want to reduce manual entry and own our content pipeline locally. "
            "Set aside about $4,500 for automation tooling.\n\n"
            "Contact: bea@saffron-studio.example\n"
        ),
    },
]


def fixture_rows() -> List[Dict[str, str]]:
    """Flat candidate rows for the seeded ``candidates.csv``."""
    rows: List[Dict[str, str]] = []
    for c in COMPANIES:
        rows.append({
            "name": c["name"],
            "website": c["website"],
            "industry": c["industry"],
            "geography": c["geography"],
            "team_size": c["team_size"],
            "contact_name": c["contact_name"],
            "contact_role": c["contact_role"],
            "contact_email": c["contact_email"],
            "notes": c["notes"],
        })
    return rows


def fixture_doc(name: str) -> str:
    """The local knowledge doc body for a company (by exact name)."""
    for c in COMPANIES:
        if c["name"] == name:
            return c["doc"]
    raise KeyError(name)


def fixture_doc_for_domain(domain: str) -> str:
    """The doc body for a company resolved by website/domain."""
    dom = (domain or "").lower()
    dom = dom.replace("https://", "").replace("http://", "").strip("/")
    for c in COMPANIES:
        if c["website"].lower().replace("https://", "").replace("http://", "").strip("/") == dom:
            return c["doc"]
    raise KeyError(domain)
