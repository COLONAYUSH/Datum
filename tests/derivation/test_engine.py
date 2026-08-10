"""DerivationEngine tests, against a real Postgres.

The properties under test are the ones the module docstring makes claims
about: backfill from an empty cursor (the Milestone A -> Milestone B shape),
incrementality (a second refresh does nothing; a supersede re-derives only
the touched record), forget propagation into views, per-view independent
cursors (a view added later backfills alone), cursor/view-write atomicity
(a failing derive advances nothing), and the namespace scoping that keeps
one tenant's refresh away from another tenant's view rows even when both
tenants hold content with the SAME record_id (content-addressing does not
salt by tenant, so this collision is legitimate and must be handled).

The view used here is a deliberately dumb CountingFakeView writing to its
own table: the engine's contract is the ViewBuilder Protocol, and testing it
through a real embedding view would smuggle that view's own behavior into
every engine assertion.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Sequence

import psycopg
import pytest

from datum.derivation.engine import DerivationEngine
from datum.derivation.views.base import RecordRow
from datum.groundstore.store import GroundStore
from datum.kernel.principal import Principal
from datum.kernel.record import ProvenanceCapsule, StructuredBody
from datum.kernel.writeop import WriteOp
from datum.storage.migrations import run_migrations
from datum.storage.wal import WAL

_DSN = os.environ.get("DATUM_PG_DSN", "postgresql://localhost/datum")
_ACME = "tenant:acme"
_OTHER = "tenant:other"


def _pg_reachable(dsn: str) -> bool:
    try:
        with psycopg.connect(dsn, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not _pg_reachable(_DSN),
    reason=f"no reachable Postgres at DATUM_PG_DSN={_DSN!r}",
)


class CountingFakeView:
    """Minimal ViewBuilder: one row per derived record in its own table, plus
    call counts so incrementality assertions can see exactly which rows the
    engine handed over (not just final table state, which delete-then-
    rederive could mask).
    """

    def __init__(self, name: str = "fake") -> None:
        self.name = name
        self.producer_version = f"{name}-v1"
        self.derived_row_ids: list[int] = []
        self.removed_row_ids: list[int] = []

    def ensure_schema(self, conn: psycopg.Connection[Any]) -> None:
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS view_{self.name} ("
            "row_id BIGINT PRIMARY KEY REFERENCES records(row_id) ON DELETE CASCADE, "
            "record_id TEXT NOT NULL, namespace TEXT NOT NULL, text TEXT NOT NULL)"
        )

    def derive(self, cur: psycopg.Cursor[Any], rows: Sequence[RecordRow]) -> int:
        for row in rows:
            self.derived_row_ids.append(row.row_id)
            cur.execute(
                f"INSERT INTO view_{self.name} (row_id, record_id, namespace, text) "
                "VALUES (%s, %s, %s, %s)",
                (
                    row.row_id,
                    str(row.record.id),
                    row.record.provenance.writer.namespace,
                    row.record.body_text(),
                ),
            )
        return len(rows)

    def remove(self, cur: psycopg.Cursor[Any], row_ids: Sequence[int]) -> int:
        self.removed_row_ids.extend(row_ids)
        cur.execute(f"DELETE FROM view_{self.name} WHERE row_id = ANY(%s)", (list(row_ids),))
        return cur.rowcount


class ExplodingView(CountingFakeView):
    """derive() raises after the remove already ran — the shape that would
    corrupt a view if the engine's batch were not one transaction.
    """

    def derive(self, cur: psycopg.Cursor[Any], rows: Sequence[RecordRow]) -> int:
        raise RuntimeError("simulated derive failure")


def _prov(namespace: str) -> ProvenanceCapsule:
    return ProvenanceCapsule(
        writer=Principal(id="ingestor", namespace=namespace),
        ingestion_path="test",
        authority_tier="UNVERIFIED",
        trust_class="trusted",
        source_version="test-v1",
    )


def _assert_op(text: str, *, source_id: str, stable_key: str, namespace: str = _ACME) -> WriteOp:
    return WriteOp.assert_(
        body=StructuredBody(text=text, section_path=(source_id, stable_key)),
        valid_from=datetime.now(timezone.utc),
        provenance=_prov(namespace),
        policy_id="default-acl",  # type: ignore[arg-type]
        source_id=source_id,
        stable_key=stable_key,
    )


def _drop_fake_views() -> None:
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS view_fake")
        conn.execute("DROP TABLE IF EXISTS view_fake2")
        conn.execute("DROP TABLE IF EXISTS view_boom")


@pytest.fixture
def store():
    run_migrations(_DSN)
    _drop_fake_views()
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE TABLE records RESTART IDENTITY CASCADE")
        conn.execute("TRUNCATE TABLE wal_entries RESTART IDENTITY")
        conn.execute("TRUNCATE TABLE view_cursors")
        conn.execute("TRUNCATE TABLE lineage_edges RESTART IDENTITY")
    wal = WAL(_DSN)
    gs = GroundStore(_DSN, wal)
    yield gs
    gs.close()
    wal.close()
    # Leave no FK-bearing table behind: other test files' fixtures TRUNCATE
    # records and would trip over a surviving fake view's foreign key.
    _drop_fake_views()


def _engine(*views: CountingFakeView) -> DerivationEngine:
    eng = DerivationEngine(_DSN, list(views))
    eng.ensure_schemas()
    return eng


def _view_rows(name: str) -> list[tuple[str, str]]:
    with psycopg.connect(_DSN, autocommit=True) as conn:
        return conn.execute(
            f"SELECT record_id, namespace FROM view_{name} ORDER BY row_id"
        ).fetchall()


def test_backfill_from_empty_cursor_derives_all_live_records(store):
    store.apply(_assert_op("alpha", source_id="docA", stable_key="s1"))
    store.apply(_assert_op("beta", source_id="docA", stable_key="s2"))
    store.apply(_assert_op("gamma", source_id="docB", stable_key="s1", namespace=_OTHER))

    view = CountingFakeView()
    with _engine(view) as eng:
        report = eng.refresh(_ACME)

    assert report.derived["fake"] == 2
    rows = _view_rows("fake")
    assert len(rows) == 2
    assert all(ns == _ACME for _, ns in rows)  # the _OTHER record stays out


def test_second_refresh_is_a_noop(store):
    store.apply(_assert_op("alpha", source_id="docA", stable_key="s1"))
    view = CountingFakeView()
    with _engine(view) as eng:
        first = eng.refresh(_ACME)
        second = eng.refresh(_ACME)
    assert first.entries["fake"] == 1
    assert second.entries["fake"] == 0
    assert second.derived["fake"] == 0
    assert view.derived_row_ids.count(view.derived_row_ids[0]) == 1  # never re-handed


def test_supersede_rederives_only_the_touched_record(store):
    store.apply(_assert_op("alpha", source_id="docA", stable_key="s1"))
    store.apply(_assert_op("beta", source_id="docA", stable_key="s2"))
    view = CountingFakeView()
    with _engine(view) as eng:
        eng.refresh(_ACME)
        derived_before = list(view.derived_row_ids)
        # Edit s1 only: same span, new content -> assert converts to supersede.
        store.apply(_assert_op("alpha EDITED", source_id="docA", stable_key="s1"))
        report = eng.refresh(_ACME)

    handed_after = view.derived_row_ids[len(derived_before):]
    assert report.derived["fake"] == 1  # only the touched span re-derived
    assert len(handed_after) == 1
    rows = _view_rows("fake")
    assert len(rows) == 2  # still one row per live span
    texts = {
        t
        for (t,) in psycopg.connect(_DSN, autocommit=True)
        .execute("SELECT text FROM view_fake")
        .fetchall()
    }
    assert texts == {"alpha EDITED", "beta"}


def test_forget_removes_the_view_rows(store):
    rid = store.apply(_assert_op("alpha", source_id="docA", stable_key="s1"))
    view = CountingFakeView()
    with _engine(view) as eng:
        eng.refresh(_ACME)
        assert len(_view_rows("fake")) == 1
        store.apply(WriteOp.forget(rid))
        report = eng.refresh(_ACME)
    assert report.removed["fake"] >= 1
    assert _view_rows("fake") == []


def test_view_added_later_backfills_independently(store):
    store.apply(_assert_op("alpha", source_id="docA", stable_key="s1"))
    first = CountingFakeView("fake")
    with _engine(first) as eng:
        eng.refresh(_ACME)

    # A second view arrives later (the Milestone B shape): it must backfill
    # from the beginning while the first view's cursor keeps it at a no-op.
    first2 = CountingFakeView("fake")
    late = CountingFakeView("fake2")
    with _engine(first2, late) as eng:
        report = eng.refresh(_ACME)
    assert report.entries["fake"] == 0
    assert report.derived["fake"] == 0
    assert report.derived["fake2"] == 1
    assert len(_view_rows("fake2")) == 1


def test_failed_derive_advances_nothing(store):
    store.apply(_assert_op("alpha", source_id="docA", stable_key="s1"))
    boom = ExplodingView("boom")
    with _engine(boom) as eng:
        with pytest.raises(RuntimeError, match="simulated derive failure"):
            eng.refresh(_ACME)
        # The batch rolled back whole: no view rows, no cursor row — the next
        # refresh starts from the beginning, nothing was skipped.
        assert _view_rows("boom") == []
        with psycopg.connect(_DSN, autocommit=True) as conn:
            cursor_rows = conn.execute(
                "SELECT * FROM view_cursors WHERE view_name='boom'"
            ).fetchall()
        assert cursor_rows == []

    # And a healthy view over the same WAL still derives it afterward.
    view = CountingFakeView("boom")  # same name: inherits the (absent) cursor
    with _engine(view) as eng:
        report = eng.refresh(_ACME)
    assert report.derived["boom"] == 1


def test_same_record_id_in_two_namespaces_stays_isolated(store):
    # Identical body + section_path in two tenants -> identical record_id.
    body = StructuredBody(text="shared text", section_path=("docA", "s1"))
    op_acme = WriteOp.assert_(
        body=body, valid_from=datetime.now(timezone.utc), provenance=_prov(_ACME),
        policy_id="default-acl", source_id="docA", stable_key="s1",  # type: ignore[arg-type]
    )
    op_other = WriteOp.assert_(
        body=body, valid_from=datetime.now(timezone.utc), provenance=_prov(_OTHER),
        policy_id="default-acl", source_id="docA", stable_key="s1",  # type: ignore[arg-type]
    )
    rid_a = store.apply(op_acme)
    # Second tenant writes through its own store instance (v1 single committer
    # per namespace); same DSN is fine for a sequential test.
    wal2 = WAL(_DSN)
    store2 = GroundStore(_DSN, wal2)
    try:
        rid_b = store2.apply(op_other)
        assert rid_a == rid_b  # the legitimate cross-tenant hash collision

        view = CountingFakeView()
        with _engine(view) as eng:
            eng.refresh(_ACME)
            eng.refresh(_OTHER)
            rows = _view_rows("fake")
            assert len(rows) == 2  # one per tenant, not one shared

            # Forgetting acme's record must not touch other's view row. An
            # UNSCOPED forget of a record live in two namespaces is refused
            # outright (fail closed on ambiguity, decisions.md #19)...
            with pytest.raises(Exception, match="refusing an ambiguous cross-tenant tombstone"):
                store.apply(WriteOp.forget(rid_a))
            # ...and the scoped forget tombstones only the acting partition.
            store.apply(WriteOp.forget(rid_a), namespace=_ACME)
            eng.refresh(_ACME)
            rows_after = _view_rows("fake")
        assert rows_after == [(str(rid_b), _OTHER)]
    finally:
        store2.close()
        wal2.close()


def test_batch_seam_derives_every_span_across_the_boundary(store):
    # More spans than _BATCH_ENTRIES (200): the WAL tail is consumed in
    # batches, and the cursor advances per batch. Nothing may be dropped at
    # the seam, and a second refresh must be a clean no-op (the cursor landed
    # exactly at the last consumed entry, not short of or past it).
    n = 450
    for i in range(n):
        store.apply(_assert_op(f"span number {i}", source_id="big", stable_key=f"s{i}"))
    view = CountingFakeView()
    with _engine(view) as eng:
        report = eng.refresh(_ACME)
        assert report.derived["fake"] == n
        assert len(_view_rows("fake")) == n
        # No id dropped or duplicated across the batch boundary.
        assert len(set(view.derived_row_ids)) == n
        second = eng.refresh(_ACME)
        assert second.entries["fake"] == 0 and second.derived["fake"] == 0


def test_lineage_edges_written_per_derivation(store):
    store.apply(_assert_op("alpha", source_id="docA", stable_key="s1"))
    view = CountingFakeView()
    with _engine(view) as eng:
        eng.refresh(_ACME)
        store.apply(_assert_op("alpha EDITED", source_id="docA", stable_key="s1"))
        eng.refresh(_ACME)
    with psycopg.connect(_DSN, autocommit=True) as conn:
        edges = conn.execute(
            "SELECT record_row_id, view_name, producer_version FROM lineage_edges ORDER BY edge_id"
        ).fetchall()
    # Two derivations (original + superseding version), two edges, append-only.
    assert len(edges) == 2
    assert all(name == "fake" and ver == "fake-v1" for _, name, ver in edges)
    assert edges[0][0] != edges[1][0]  # distinct physical rows
