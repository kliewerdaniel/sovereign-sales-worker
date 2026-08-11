"""Company knowledge — the Hermes Atlas bridge.

Atlas (~/Documents/Projects/hermes-atlas) already implements compile-time
knowledge: ingest -> extract -> entities/claims/relationships/contradictions ->
confidence -> evidence ledger, with an append-only changelog and a determinism
gate. We do NOT reimplement any of that. This module:

  1. locates Atlas (``SWORKER_ATLAS_HOME`` or the sibling checkout) and imports it;
  2. compiles ``company/**.md`` into a store under ``<workspace>/.state/atlas``;
  3. exposes retrieval as Worker tools that return RETRIEVED-provenance evidence
     pointing at real claim ids and real source files.

If Atlas is not importable, knowledge degrades to deterministic grep over the
company markdown — degraded, clearly labelled, never silently fabricated.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

ATLAS_AVAILABLE = False
_ATLAS_ERR = ""


def _try_import() -> bool:
    global ATLAS_AVAILABLE, _ATLAS_ERR
    if ATLAS_AVAILABLE:
        return True
    candidates = []
    env = os.environ.get("SWORKER_ATLAS_HOME")
    if env:
        candidates.append(env)
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates.append(os.path.join(os.path.dirname(here), "hermes-atlas"))
    for c in candidates:
        if c and os.path.isdir(os.path.join(c, "hermes_atlas")) and c not in sys.path:
            sys.path.insert(0, c)
    try:
        import hermes_atlas  # noqa: F401

        ATLAS_AVAILABLE = True
    except Exception as exc:  # pragma: no cover
        _ATLAS_ERR = f"{type(exc).__name__}: {exc}"
        ATLAS_AVAILABLE = False
    return ATLAS_AVAILABLE


def atlas_status() -> Dict[str, Any]:
    ok = _try_import()
    info: Dict[str, Any] = {"available": ok, "error": _ATLAS_ERR}
    if ok:
        import hermes_atlas

        info["version"] = hermes_atlas.__version__
        info["path"] = os.path.dirname(os.path.abspath(hermes_atlas.__file__ or ""))
    return info


# ---------------------------------------------------------------------------
# compilation
# ---------------------------------------------------------------------------


def _collect_markdown(roots: List[str]) -> List[str]:
    files: List[str] = []
    for root in roots:
        if os.path.isfile(root) and root.endswith(".md"):
            files.append(os.path.abspath(root))
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in sorted(dirnames) if not d.startswith(".")]
            for fn in sorted(filenames):
                if fn.endswith(".md") and not fn.startswith((".", "_")):
                    files.append(os.path.join(dirpath, fn))
    return sorted(set(files))


def compile_knowledge(
    knowledge_roots: List[str], atlas_dir: str, *, client=None, summarize: bool = False
) -> Dict[str, Any]:
    """Compile company markdown into an Atlas store. Incremental by construction:
    Atlas skips re-extraction for sources whose checksum is unchanged."""
    if not _try_import():
        return {"ok": False, "reason": "atlas-unavailable", "error": _ATLAS_ERR}
    from hermes_atlas.compiler import Compiler
    from hermes_atlas.ingest import ingest_file
    from hermes_atlas.store import AtlasStore

    files = _collect_markdown(knowledge_roots)
    if not files:
        return {"ok": False, "reason": "no-markdown", "roots": knowledge_roots}
    sources = []
    for f in files:
        try:
            rec = ingest_file(f)
        except OSError:
            continue
        if len(rec.get("text", "").strip()) < 40:
            continue
        sources.append(rec)
    store = AtlasStore(atlas_dir)
    cycle = len([c for c in store.changelog() if c.get("op") == "note"]) + 1
    report = Compiler(store, client=client).compile(
        sources, cycle=cycle, incremental=True, summarize=summarize
    )
    stats = store.stats()
    return {
        "ok": True,
        "atlas_dir": atlas_dir,
        "files": len(files),
        "sources": len(sources),
        "stats": stats,
        "report": dict(report),
        "fingerprint": store.fingerprint(),
    }


# ---------------------------------------------------------------------------
# retrieval
# ---------------------------------------------------------------------------


def _tokens(q: str) -> List[str]:
    import re

    stop = {
        "the", "a", "an", "of", "for", "and", "or", "to", "in", "on", "is", "are",
        "what", "why", "how", "do", "does", "we", "our", "i", "this", "that", "about",
    }
    return [t for t in re.findall(r"[a-z0-9]+", q.lower()) if len(t) > 2 and t not in stop]


def search_claims(atlas_dir: str, query: str, limit: int = 8) -> List[Dict[str, Any]]:
    """Deterministic token-overlap search over compiled claims.

    Ranking is BM25-ish but intentionally simple and reproducible: identical
    inputs always produce identical ordering, which the determinism tests rely on.
    """
    if not _try_import() or not os.path.isdir(atlas_dir):
        return []
    from hermes_atlas.store import AtlasStore

    store = AtlasStore(atlas_dir)
    toks = _tokens(query)
    if not toks:
        return []
    sources = {s["id"]: s for s in store.read_all("sources")}
    scored: List[Tuple[float, str, Dict[str, Any]]] = []
    for claim in store.read_all("claims"):
        text = (claim.get("text") or "").lower()
        hits = sum(1 for t in toks if t in text)
        if not hits:
            continue
        score = hits / len(toks) + 0.15 * float(claim.get("confidence") or 0.0)
        scored.append((score, claim["id"], claim))
    scored.sort(key=lambda x: (-x[0], x[1]))
    out = []
    for score, cid, claim in scored[:limit]:
        srcs = [sources.get(s, {}) for s in (claim.get("source_ids") or [])]
        out.append(
            {
                "claim_id": cid,
                "text": claim.get("text", ""),
                "confidence": claim.get("confidence"),
                "status": claim.get("status", ""),
                "stance": claim.get("stance", ""),
                "hedged": claim.get("hedged", False),
                "contradiction_ids": claim.get("contradiction_ids") or [],
                "score": round(score, 4),
                "sources": [
                    {"id": s.get("id", ""), "title": s.get("title", ""), "path": s.get("path", "")}
                    for s in srcs
                    if s
                ],
            }
        )
    return out


def explain_claim(atlas_dir: str, claim_id: str) -> Optional[Dict[str, Any]]:
    if not _try_import():
        return None
    from hermes_atlas.explain import explain_claim as _explain
    from hermes_atlas.store import AtlasStore

    return _explain(AtlasStore(atlas_dir), claim_id)


def grep_knowledge(roots: List[str], query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Degraded fallback used when Atlas is unavailable. Clearly labelled."""
    toks = _tokens(query)
    hits: List[Dict[str, Any]] = []
    for path in _collect_markdown(roots):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            low = line.lower()
            n = sum(1 for t in toks if t in low)
            if n:
                hits.append(
                    {"path": path, "line": i, "text": line.strip()[:300], "score": n / max(len(toks), 1)}
                )
    hits.sort(key=lambda h: (-h["score"], h["path"], h["line"]))
    return hits[:limit]
