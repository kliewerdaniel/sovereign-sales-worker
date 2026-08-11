"""Tests for the company-knowledge bridge (sworker.knowledge + tools.knowledge).

Covers both retrieval paths without a network or a real Atlas install:

  * BLACK path  -> Atlas not importable -> deterministic grep over company/*.md,
    clearly labelled "[degraded: raw document grep, knowledge not compiled]".
  * COMPILED path -> a minimal fake `hermes_atlas` package is injected on
    sys.path so the compiled-claim retrieval branch runs end to end.

Run with:  env -u PYTHONPATH -u PYTHONHOME /opt/homebrew/bin/python3.14 -m pytest tests/
"""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

import pytest

from sworker.config import Workspace
from sworker.tools.base import ToolContext
from sworker.tools.knowledge import KnowledgeSearch, KnowledgeExplain


MD_NOTE = textwrap.dedent(
    """\
    # Acme Coffee — Pricing Policy

    We grant a 10% volume discount to partners ordering above 500 units.
    Free shipping applies only to repeat customers.
    """
)


@pytest.fixture()
def ws(tmp_path):
    home = tmp_path / "acme"
    (home / "company").mkdir(parents=True)
    (home / "company" / "pricing.md").write_text(MD_NOTE)
    (home / "workers").mkdir(parents=True)
    w = Workspace(str(home))
    w.ensure()
    return w


def _ctx(ws: Workspace) -> ToolContext:
    return ToolContext(
        worker="acme-analyst",
        run_id="run_test",
        workspace=str(ws.root),
        fs_roots=[str(Path(ws.root) / "company")],
        artifacts_dir=str(Path(ws.root) / "artifacts"),
    )


def test_black_path_degraded_grep(ws):
    """No Atlas importable -> labelled grep, never silent fabrication."""
    # Ensure Atlas is not resolvable for this test regardless of checkout layout.
    os.environ.pop("SWORKER_ATLAS_HOME", None)
    import importlib

    import sworker.knowledge as K

    importlib.reload(K)  # reset cached ATLAS_AVAILABLE
    assert K.ATLAS_AVAILABLE is False, "expected Atlas unavailable in this env"

    ctx = _ctx(ws)
    res = KnowledgeSearch().run(ctx, {"query": "volume discount"})
    assert res.ok
    assert res.data["mode"] == "grep"
    assert "[degraded: raw document grep, knowledge not compiled]" in res.output
    assert "10% volume discount" in res.output
    # grep evidence points at the real file:line, not a fabricated claim id
    assert res.evidence and res.evidence[0]["source_ref"].endswith(":1") or any(
        "pricing.md" in e["source_ref"] for e in res.evidence
    )


def test_compiled_path_returns_claims(tmp_path):
    """A minimal fake hermes_atlas yields compiled-claim retrieval.

    We drop a fake package on sys.path and point SWORKER_ATLAS_HOME at it so
    knowledge._try_import picks it up. The fake exposes just enough of the
    Atlas store API for search_claims to run deterministically.
    """
    atlas_home = tmp_path / "hermes-atlas"
    (atlas_home / "hermes_atlas").mkdir(parents=True)
    (atlas_home / "hermes_atlas" / "__init__.py").write_text("__version__ = '0.0.0'\n")
    (atlas_home / "hermes_atlas" / "store.py").write_text(
        textwrap.dedent(
            """\
            class AtlasStore:
                def __init__(self, path): pass
                def read_all(self, table):
                    if table == "claims":
                        return [{"id": "c1", "text": "acme grants a volume discount",
                                 "confidence": 0.9, "source_ids": ["s1"]}]
                    if table == "sources":
                        return [{"id": "s1", "title": "Pricing Policy",
                                 "path": "company/pricing.md"}]
                    return []
            """
        )
    )
    # The real Atlas checkout may already be imported/cached this session; force
    # the fake onto sys.path AND evict any cached hermes_atlas so `import
    # hermes_atlas` resolves to our stub instead of the sibling project.
    fake_pkg = str(atlas_home)
    sys.path.insert(0, fake_pkg)
    for m in [k for k in sys.modules if k == "hermes_atlas" or k.startswith("hermes_atlas.")]:
        sys.modules.pop(m, None)
    os.environ["SWORKER_ATLAS_HOME"] = str(atlas_home)
    # Force re-import of the knowledge module so it discovers the fake Atlas.
    import importlib

    import sworker.knowledge as K

    importlib.reload(K)
    assert K.atlas_status()["available"] is True

    company = tmp_path / "company"
    company.mkdir(parents=True)
    (company / "pricing.md").write_text(MD_NOTE)

    # Build a workspace free of .state/atlas so search hits the compiled branch.
    ws_home = tmp_path / "acme"
    ws_home.mkdir()
    (ws_home / "company").mkdir(parents=True)
    (ws_home / "company" / "pricing.md").write_text(MD_NOTE)
    # search_claims only reads compiled claims when the compiled store exists.
    (ws_home / ".state" / "atlas").mkdir(parents=True)
    from sworker.config import Workspace

    ws = Workspace(str(ws_home))
    ws.ensure()
    ctx = _ctx(ws)

    res = KnowledgeSearch().run(ctx, {"query": "volume discount"})
    assert res.ok
    assert res.data["mode"] == "compiled", res.data
    assert res.data["count"] >= 1
    assert "acme grants a volume discount" in res.output
    # compiled evidence references the real claim id, not grep coordinates
    assert res.evidence and res.evidence[0]["source_ref"] == "c1"
    assert res.evidence[0].get("atlas_claim") is True

    # cleanup: drop the env override + fake path so they don't leak into other tests
    os.environ.pop("SWORKER_ATLAS_HOME", None)
    if fake_pkg in sys.path:
        sys.path.remove(fake_pkg)
    for m in [k for k in sys.modules if k == "hermes_atlas" or k.startswith("hermes_atlas.")]:
        sys.modules.pop(m, None)
    importlib.reload(K)


def test_knowledge_explain_handles_missing_claim(ws):
    """Explaining an unknown claim returns a clean failure, not an exception."""
    ctx = _ctx(ws)
    res = KnowledgeExplain().run(ctx, {"claim_id": "does-not-exist"})
    assert res.ok is False
    assert "does-not-exist" in res.error
