"""Tests for L1 WAL, run against a real Postgres.

These tests need an actual database (DATUM_PG_DSN, or the default
postgresql://localhost/datum) -- this is not mocked, per FRAMEWORK.md's own
framing of the WAL as forty years of write-ahead-logging discipline
delegated to Postgres itself, not reimplemented here. `testpaths =
["tests"]` in pyproject.toml means every other module's test suite collects
this file too, so a missing/unreachable database must skip cleanly at
collection/fixture time rather than error every other agent's run: see
`_pg_reachable()` and the module-level skipif below.

Each test gets its own freshly migrated, freshly truncated `wal_entries`
table via the `wal` fixture, so tests are independent of each other and of
run order.

Read API (post-review, decisions.md #14 + module docstring): the resumable
`tail_since` requires a namespace; the one-shot global read is `scan()`.
`test_concurrent_single_namespace_writers_lose_nothing` is the regression
test for review finding 17 (the ordering suite previously only ran
single-connection sequential appends, so it never exercised the concurrent
shape the module makes a safety claim about).
"""

from __future__ import annotations

import os
import threading

import psycopg
import pytest

from datum.storage.migrations import run_migrations
from datum.storage.wal import WAL

_DSN = os.environ.get("DATUM_PG_DSN", "postgresql://localhost/datum")

_ACME = "tenant:acme"


def _pg_reachable(dsn: str) -> bool:
    try:
        with psycopg.connect(dsn, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not _pg_reachable(_DSN),
    reason=f"no reachable Postgres at DATUM_PG_DSN={_DSN!r}; set DATUM_PG_DSN "
    "to a real database to run WAL tests",
)


@pytest.fixture
def wal():
    run_migrations(_DSN)
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE TABLE wal_entries RESTART IDENTITY")
    instance = WAL(_DSN)
    yield instance
    instance.close()


def test_append_returns_monotonically_increasing_ids(wal):
    ids = [wal.append({"n": i}, namespace=_ACME) for i in range(5)]
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)


def test_tail_since_none_returns_everything_in_order(wal):
    for i in range(5):
        wal.append({"n": i}, namespace=_ACME)
    entries = list(wal.tail_since(None, namespace=_ACME))
    assert [e["payload"]["n"] for e in entries] == [0, 1, 2, 3, 4]
    assert [e["tx_id"] for e in entries] == sorted(e["tx_id"] for e in entries)


def test_tail_since_marker_returns_only_the_tail(wal):
    ids = [wal.append({"n": i}, namespace=_ACME) for i in range(5)]
    tail = list(wal.tail_since(ids[2], namespace=_ACME))
    assert [e["payload"]["n"] for e in tail] == [3, 4]


def test_tail_since_marker_at_last_id_returns_nothing(wal):
    ids = [wal.append({"n": i}, namespace=_ACME) for i in range(3)]
    assert list(wal.tail_since(ids[-1], namespace=_ACME)) == []


def test_tail_since_requires_a_namespace(wal):
    # The resumable tail must not offer an all-namespace mode (decisions.md
    # #14): a resumable global tail is the one shape the review proved unsafe.
    with pytest.raises(TypeError):
        list(wal.tail_since(None))  # type: ignore[call-arg]


def test_namespace_filter_isolates_entries(wal):
    wal.append({"n": 1}, namespace=_ACME)
    wal.append({"n": 2}, namespace="tenant:other")
    wal.append({"n": 3}, namespace=_ACME)

    acme = list(wal.tail_since(None, namespace=_ACME))
    other = list(wal.tail_since(None, namespace="tenant:other"))

    assert [e["payload"]["n"] for e in acme] == [1, 3]
    assert [e["namespace"] for e in acme] == [_ACME, _ACME]
    assert [e["payload"]["n"] for e in other] == [2]


def test_scan_reads_all_namespaces_from_the_beginning(wal):
    wal.append({"n": 1}, namespace=_ACME)
    wal.append({"n": 2}, namespace="tenant:other")
    wal.append({"n": 3}, namespace=_ACME)
    everything = list(wal.scan())
    assert [e["payload"]["n"] for e in everything] == [1, 2, 3]
    # scan takes no marker — it is one-shot, not resumable (decisions.md #14).
    assert "marker" not in wal.scan.__doc__.lower() or "no marker" in wal.scan.__doc__.lower()


def test_scan_can_filter_to_one_namespace(wal):
    wal.append({"n": 1}, namespace=_ACME)
    wal.append({"n": 2}, namespace="tenant:other")
    assert [e["payload"]["n"] for e in wal.scan(namespace=_ACME)] == [1]


def test_tail_since_respects_batch_size_pagination(wal):
    for i in range(7):
        wal.append({"n": i}, namespace=_ACME)
    entries = list(wal.tail_since(None, namespace=_ACME, batch_size=2))
    assert [e["payload"]["n"] for e in entries] == list(range(7))


def test_payload_round_trips_nested_json(wal):
    payload = {"kind": "assert", "meta": {"page": 3, "tags": ["a", "b"]}, "ok": True}
    wal.append(payload, namespace=_ACME)
    (got,) = list(wal.tail_since(None, namespace=_ACME))
    assert got["payload"] == payload


def test_created_at_is_populated_and_monotonic_non_decreasing(wal):
    for i in range(3):
        wal.append({"n": i}, namespace=_ACME)
    entries = list(wal.tail_since(None, namespace=_ACME))
    timestamps = [e["created_at"] for e in entries]
    assert all(t is not None for t in timestamps)
    assert timestamps == sorted(timestamps)


def test_tail_since_supports_resuming_from_the_last_tx_id_seen(wal):
    """The round trip the future since() MCP verb depends on: consume the
    tail, remember the last tx_id, append something new, confirm a fresh
    call picks up exactly the new entry -- tx_id as a genuine resumable
    cursor, not just an ordering key within one call.
    """
    for i in range(3):
        wal.append({"n": i}, namespace=_ACME)

    first_batch = list(wal.tail_since(None, namespace=_ACME))
    last_tx_id = first_batch[-1]["tx_id"]

    wal.append({"n": "new"}, namespace=_ACME)

    resumed = list(wal.tail_since(last_tx_id, namespace=_ACME))
    assert len(resumed) == 1
    assert resumed[0]["payload"]["n"] == "new"
    assert resumed[0]["tx_id"] > last_tx_id


def test_append_in_txn_participates_in_the_callers_transaction(wal):
    """The L1<->L2 seam (decisions.md #11): a WAL append made on a caller's
    cursor commits with the caller's transaction, and rolls back with it.
    """
    # Committed path: append inside an explicit transaction, then commit.
    with psycopg.connect(_DSN) as conn:
        with conn.transaction():
            tx_id = wal.append_in_txn(conn.cursor(), {"n": "committed"}, namespace=_ACME)
        assert isinstance(tx_id, int)
    assert any(e["payload"].get("n") == "committed" for e in wal.tail_since(None, namespace=_ACME))

    # Rolled-back path: the append must vanish with the aborted transaction.
    before = [e["tx_id"] for e in wal.tail_since(None, namespace=_ACME)]
    with psycopg.connect(_DSN) as conn:
        try:
            with conn.transaction():
                wal.append_in_txn(conn.cursor(), {"n": "rolled-back"}, namespace=_ACME)
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass
    after = list(wal.tail_since(None, namespace=_ACME))
    assert not any(e["payload"].get("n") == "rolled-back" for e in after)
    # nothing else was lost by the rollback
    assert [e["tx_id"] for e in after] == before


def test_concurrent_single_namespace_writers_lose_nothing(wal):
    """Finding 17 regression: two threads appending concurrently to the SAME
    namespace, then a full resumable drain, must surface every committed
    entry exactly once. This is v1's single-committer-per-namespace invariant
    stressed from two threads through separate connections; because they hit
    one namespace the per-namespace tail must still be loss-free once all
    writers have finished and the reader drains to the end.
    """
    n_per_writer = 200
    barrier = threading.Barrier(2)

    def writer(tag: str) -> None:
        w = WAL(_DSN)
        try:
            barrier.wait()
            for i in range(n_per_writer):
                w.append({"tag": tag, "i": i}, namespace=_ACME)
        finally:
            w.close()

    t1 = threading.Thread(target=writer, args=("a",))
    t2 = threading.Thread(target=writer, args=("b",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    drained = list(wal.tail_since(None, namespace=_ACME))
    assert len(drained) == 2 * n_per_writer
    seen = {(e["payload"]["tag"], e["payload"]["i"]) for e in drained}
    expected = {(tag, i) for tag in ("a", "b") for i in range(n_per_writer)}
    assert seen == expected
    # ids strictly increasing across the full drain
    ids = [e["tx_id"] for e in drained]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)


def test_run_migrations_is_idempotent():
    run_migrations(_DSN)
    run_migrations(_DSN)  # must not raise on a second run
