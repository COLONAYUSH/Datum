"""L2 GroundStore tests, against a real Postgres.

The load-bearing ones are the CAS/atomic-supersede correctness tests and, above
all, `test_concurrent_asserts_to_the_same_span_yield_exactly_one_live_record`
— the direct regression for the write-race the whole design exists to close
(Mem0 #4892 / paper Figure 5). Not mocked: the invariant is enforced by a
Postgres partial unique index, so a mock would test nothing that matters.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone

import psycopg
import pytest

from datum.groundstore.store import GroundStore, compute_record_id, require_writer_namespace
from datum.kernel.errors import AdmissionError, DatumError
from datum.kernel.principal import Principal
from datum.kernel.record import ProvenanceCapsule, StructuredBody
from datum.kernel.writeop import WriteOp
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
    reason=f"no reachable Postgres at DATUM_PG_DSN={_DSN!r}",
)


def _prov(namespace: str = _ACME, *, tier: str = "UNVERIFIED", trust: str = "trusted") -> ProvenanceCapsule:
    return ProvenanceCapsule(
        writer=Principal(id="ingestor", namespace=namespace),
        ingestion_path="pdf_upload",
        authority_tier=tier,  # type: ignore[arg-type]
        trust_class=trust,  # type: ignore[arg-type]
        source_version="docling-2.4",
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


@pytest.fixture
def store():
    run_migrations(_DSN)
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE TABLE records RESTART IDENTITY CASCADE")
        conn.execute("TRUNCATE TABLE wal_entries RESTART IDENTITY")
    wal = WAL(_DSN)
    gs = GroundStore(_DSN, wal)
    yield gs
    gs.close()
    wal.close()


def _count_live(source_id: str, stable_key: str) -> int:
    with psycopg.connect(_DSN, autocommit=True) as conn:
        row = conn.execute(
            "SELECT count(*) FROM records WHERE source_id=%s AND stable_key=%s AND tx_to IS NULL",
            (source_id, stable_key),
        ).fetchone()
    return row[0]


def test_assert_creates_a_live_record_findable_by_span(store):
    rid = store.apply(_assert_op("hello world", source_id="docA", stable_key="s1"))
    assert rid == compute_record_id(StructuredBody(text="hello world", section_path=("docA", "s1")), "chunk")
    found = store.find_span("docA", "s1", namespace=_ACME)
    assert found is not None
    assert found.body_text() == "hello world"
    assert found.is_live
    assert found.supersedes is None


def test_reasserting_identical_content_is_an_idempotent_noop(store):
    op = _assert_op("same text", source_id="docA", stable_key="s1")
    rid1 = store.apply(op)
    rid2 = store.apply(op)  # identical content, same span
    assert rid1 == rid2
    assert _count_live("docA", "s1") == 1  # not duplicated


def test_asserting_new_content_for_a_live_span_converts_to_supersede(store):
    r1 = store.apply(_assert_op("version one", source_id="docA", stable_key="s1"))
    r2 = store.apply(_assert_op("version two", source_id="docA", stable_key="s1"))
    assert r1 != r2
    assert _count_live("docA", "s1") == 1  # exactly one live, not two
    live = store.find_span("docA", "s1", namespace=_ACME)
    assert live is not None and live.body_text() == "version two"
    assert live.supersedes == r1  # the new live points back at the one it replaced


def test_explicit_supersede_closes_old_and_opens_new_atomically(store):
    r1 = store.apply(_assert_op("original", source_id="docA", stable_key="s1"))
    op = WriteOp.supersede(
        old_id=r1,
        body=StructuredBody(text="revised", section_path=("docA", "s1")),
        valid_from=datetime.now(timezone.utc),
        provenance=_prov(),
        source_id="docA",
        stable_key="s1",
    )
    r2 = store.apply(op)
    assert _count_live("docA", "s1") == 1
    live = store.find_span("docA", "s1", namespace=_ACME)
    assert live is not None and live.id == r2 and live.body_text() == "revised"
    # the old version is retained as history (not deleted), now non-live
    assert store.get_live(r1) is None


def test_superseding_a_non_live_record_fails_loudly(store):
    r1 = store.apply(_assert_op("v1", source_id="docA", stable_key="s1"))
    store.apply(_assert_op("v2", source_id="docA", stable_key="s1"))  # r1 no longer live
    op = WriteOp.supersede(
        old_id=r1,
        body=StructuredBody(text="v3", section_path=("docA", "s1")),
        valid_from=datetime.now(timezone.utc),
        provenance=_prov(),
        source_id="docA",
        stable_key="s1",
    )
    with pytest.raises(DatumError):
        store.apply(op)  # refuses to create a second live version


def test_forget_tombstones_the_record_but_keeps_history(store):
    rid = store.apply(_assert_op("secret", source_id="docA", stable_key="s1"))
    receipt = store.apply(WriteOp.forget(rid))
    assert receipt.mode == "tombstone"
    assert receipt.key_shredded_at is None
    assert store.find_span("docA", "s1", namespace=_ACME) is None  # no longer live
    assert store.get_live(rid) is None
    # history row remains (tombstone, not delete)
    with psycopg.connect(_DSN, autocommit=True) as conn:
        total = conn.execute("SELECT count(*) FROM records WHERE record_id=%s", (rid,)).fetchone()[0]
    assert total == 1


def test_forgetting_a_non_live_record_fails_loudly(store):
    with pytest.raises(DatumError):
        store.apply(WriteOp.forget("rec_does_not_exist"))  # type: ignore[arg-type]


def test_namespace_is_materialized_from_the_writer_and_isolates_reads(store):
    store.apply(_assert_op("acme doc", source_id="docA", stable_key="s1", namespace=_ACME))
    store.apply(_assert_op("other doc", source_id="docB", stable_key="s1", namespace="tenant:other"))
    acme = [r.body_text() for r in store.live_in_namespace(_ACME)]
    other = [r.body_text() for r in store.live_in_namespace("tenant:other")]
    assert acme == ["acme doc"]
    assert other == ["other doc"]


def test_each_write_appends_one_wal_entry_atomically(store):
    store.apply(_assert_op("a", source_id="docA", stable_key="s1"))
    store.apply(_assert_op("b", source_id="docA", stable_key="s2"))
    entries = list(store._wal.tail_since(None, namespace=_ACME))
    ops = [e["payload"]["op"] for e in entries]
    assert ops == ["assert", "assert"]


def test_structured_body_round_trips_through_the_store(store):
    from datum.kernel.record import BoundingBox, Span, TableCell

    body = StructuredBody(
        text="Cell A1 | Cell B1",
        section_path=("Report", "§2 Results"),
        page=4,
        bbox=BoundingBox(page=4, x0=1.0, y0=2.0, x1=3.0, y1=4.0),
        table_cells=(TableCell(row=0, col=0, text="Cell A1", is_header=True),),
        span=Span(start=100, end=117),
    )
    op = WriteOp.assert_(
        body=body, valid_from=datetime.now(timezone.utc), provenance=_prov(),
        policy_id="default-acl", source_id="docA", stable_key="s1",  # type: ignore[arg-type]
    )
    store.apply(op)
    got = store.find_span("docA", "s1", namespace=_ACME)
    assert isinstance(got.body, StructuredBody)
    assert got.body.section_path == ("Report", "§2 Results")
    assert got.body.page == 4
    assert got.body.bbox == body.bbox
    assert got.body.table_cells == body.table_cells
    assert got.body.span == body.span


def test_require_writer_namespace_refuses_cross_namespace_write():
    p = Principal(id="alice", namespace=_ACME)
    op = _assert_op("x", source_id="docA", stable_key="s1", namespace="tenant:other")
    with pytest.raises(AdmissionError):
        require_writer_namespace(op, p)
    # same-namespace write is allowed
    ok = _assert_op("x", source_id="docA", stable_key="s1", namespace=_ACME)
    require_writer_namespace(ok, p)  # no raise


def test_concurrent_asserts_to_the_same_span_yield_exactly_one_live_record():
    """THE write-race regression (Mem0 #4892 / paper Figure 5). Two writers,
    each its own GroundStore/connection, race to create the SAME new span at
    the same instant. The partial unique index must arbitrate so that exactly
    one live record exists afterward — never two, never zero, never a
    corrupted index — regardless of who won. This is the property the paper
    claims and the design's central write-path bet.
    """
    run_migrations(_DSN)
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE TABLE records RESTART IDENTITY CASCADE")
        conn.execute("TRUNCATE TABLE wal_entries RESTART IDENTITY")

    n_rounds = 40
    errors: list[Exception] = []
    # One barrier per round: threading.Barrier is single-use once tripped, so
    # a fresh one per span is what actually forces both threads to collide on
    # the SAME span at the SAME instant, round after round.
    barriers = [threading.Barrier(2) for _ in range(n_rounds)]

    def writer(text: str) -> None:
        wal = WAL(_DSN)
        gs = GroundStore(_DSN, wal)
        try:
            for i in range(n_rounds):
                barriers[i].wait()
                try:
                    gs.apply(_assert_op(text, source_id="docA", stable_key=f"s{i}"))
                except DatumError:
                    # A converted-supersede loser can legitimately raise on a
                    # tight race (trying to supersede a row the other writer
                    # just superseded): a loud, correct failure, not
                    # corruption. The one-live invariant below must hold
                    # regardless of who raised.
                    pass
        except Exception as exc:  # pragma: no cover - surfaced via `errors`
            errors.append(exc)
        finally:
            gs.close()
            wal.close()

    t1 = threading.Thread(target=writer, args=("from-writer-1",))
    t2 = threading.Thread(target=writer, args=("from-writer-2",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert errors == [], f"unexpected errors under concurrency: {errors}"
    # The invariant: every contested span ends with exactly one live record.
    with psycopg.connect(_DSN, autocommit=True) as conn:
        for i in range(n_rounds):
            live = conn.execute(
                "SELECT count(*) FROM records WHERE source_id='docA' AND stable_key=%s "
                "AND tx_to IS NULL",
                (f"s{i}",),
            ).fetchone()[0]
            assert live == 1, f"span s{i} has {live} live records, expected exactly 1"


def test_concurrent_asserts_to_the_same_span_in_different_namespaces_do_not_contend():
    """The namespace-scoped-span counterpart to the write-race test
    (decisions.md #19; migration 0005 rebuilt the unique index as
    (namespace, source_id, stable_key)). Two writers in DIFFERENT namespaces
    race to create the SAME (source_id, stable_key) with IDENTICAL content —
    so both compute the SAME content-addressed record_id — at the same
    instant. The partition scoping must let BOTH stay live (one per
    namespace): a tenant's write is never starved by an unrelated tenant that
    happens to have chosen the same source id, and the shared record_id does
    NOT collapse them into one row.
    """
    run_migrations(_DSN)
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE TABLE records RESTART IDENTITY CASCADE")
        conn.execute("TRUNCATE TABLE wal_entries RESTART IDENTITY")

    n_rounds = 40
    other = "tenant:other"
    errors: list[Exception] = []
    barriers = [threading.Barrier(2) for _ in range(n_rounds)]

    def writer(namespace: str) -> None:
        wal = WAL(_DSN)
        gs = GroundStore(_DSN, wal)
        try:
            for i in range(n_rounds):
                barriers[i].wait()
                # Identical text + span in both namespaces => identical
                # record_id; the only difference is the writer's namespace.
                gs.apply(_assert_op("shared content", source_id="docA", stable_key=f"s{i}", namespace=namespace))
        except Exception as exc:  # pragma: no cover - surfaced via `errors`
            errors.append(exc)
        finally:
            gs.close()
            wal.close()

    t1 = threading.Thread(target=writer, args=(_ACME,))
    t2 = threading.Thread(target=writer, args=(other,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert errors == [], f"cross-namespace writers contended unexpectedly: {errors}"
    with psycopg.connect(_DSN, autocommit=True) as conn:
        for i in range(n_rounds):
            rows = conn.execute(
                "SELECT namespace FROM records WHERE source_id='docA' AND stable_key=%s "
                "AND tx_to IS NULL ORDER BY namespace",
                (f"s{i}",),
            ).fetchall()
            namespaces = [r[0] for r in rows]
            assert namespaces == [_ACME, other], (
                f"span s{i}: expected one live record per namespace {[_ACME, other]}, got {namespaces}"
            )
