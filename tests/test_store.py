"""Hardening tests for WorkerStore SQL building.

The table/column/order identifiers are interpolated into SQL via f-strings, so
they must be allowlist-checked. Every current call site passes literals, but
these tests lock in the contract that an unknown table / column / order is
rejected with ValueError rather than silently interpolated.
"""

from __future__ import annotations

import pytest

from sworker.config import Workspace
from sworker.store import WorkerStore


@pytest.fixture()
def store(tmp_path):
    ws = Workspace(str(tmp_path / "ws"))
    ws.ensure()
    return WorkerStore(ws.state_dir)


def test_unknown_table_rejected(store):
    with pytest.raises(ValueError):
        store.get("nonexistent", "x")
    with pytest.raises(ValueError):
        store.find("nonexistent")
    with pytest.raises(ValueError):
        store.put("nonexistent", {"id": "x"})


def test_unknown_where_column_rejected(store):
    with pytest.raises(ValueError):
        store.find("runs", not_a_column="y")


def test_unknown_order_rejected(store):
    # 'created' is the implicit default and is allowed; an arbitrary column is not.
    with pytest.raises(ValueError):
        store.find("runs", order="not_a_column")


def test_known_order_accepted(store):
    # Should not raise for a real indexed column.
    assert store.find("runs", order="seq") == []
    assert store.find("runs", order="started") == []


def test_known_columns_work(store):
    # Smoke that the allowlist does not break legitimate queries.
    run = {"id": "run_1", "worker": "w", "status": "SUCCESS", "seq": 1}
    store.put("runs", run)
    assert store.get("runs", "run_1")["worker"] == "w"
    assert store.find("runs", worker="w")[0]["id"] == "run_1"
