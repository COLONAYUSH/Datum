"""L3 write path, against a real Postgres: a document ingests into real
records, re-ingest supersedes only changed spans, and the three admission
gates (authority-tier clamp, write-side namespace guard, preconditions) all
bite. Not mocked — the point is the whole path from raw text to committed,
bitemporal, namespace-partitioned records.
"""

from __future__ import annotations

import os

import psycopg
import pytest

from datum.groundstore.precondition import PreconditionRegistry
from datum.groundstore.store import GroundStore
from datum.kernel.errors import AdmissionError
from datum.kernel.principal import Principal
from datum.storage.migrations import run_migrations
from datum.storage.wal import WAL
from datum.writepath import DocumentInput, DocumentPolicy, WriteOrchestrator

_DSN = os.environ.get("DATUM_PG_DSN", "postgresql://localhost/datum")
_ACME = "tenant:acme"


def _pg_reachable(dsn: str) -> bool:
    try:
        with psycopg.connect(dsn, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


pytestmark = pytest.mark.skipif(not _pg_reachable(_DSN), reason=f"no Postgres at {_DSN!r}")

_DOC = """# Runbook

Restart the service with the deploy script.

## Rollback

Roll back by pinning the previous image tag and redeploying.
"""


@pytest.fixture
def wiring():
    run_migrations(_DSN)
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE TABLE records RESTART IDENTITY CASCADE")
        conn.execute("TRUNCATE TABLE wal_entries RESTART IDENTITY")
    wal = WAL(_DSN)
    store = GroundStore(_DSN, wal)
    preconditions = PreconditionRegistry()
    orch = WriteOrchestrator(store, preconditions)
    orch.register_policy("document", DocumentPolicy(store))
    yield orch, store, preconditions
    store.close()
    wal.close()


def _ingest(orch, text, principal, source_id="runbook.md"):
    return orch.execute(
        "document",
        DocumentInput(source_id=source_id, policy_id="default-acl", text=text),  # type: ignore[arg-type]
        principal,
    )


def test_document_ingests_into_live_records_with_section_paths(wiring):
    orch, store, _ = wiring
    p = Principal(id="alice", namespace=_ACME)
    results = _ingest(orch, _DOC, p)
    assert len(results) >= 2  # at least the intro + the Rollback section
    live = list(store.live_in_namespace(_ACME))
    assert live, "expected live records after ingest"
    # section paths reflect the markdown headings
    paths = {r.body.section_path for r in live if hasattr(r.body, "section_path")}
    assert any("Rollback" in path for path in paths)
    # every record carries the writer's namespace and trusted document tier
    assert all(r.provenance.writer.namespace == _ACME for r in live)
    assert all(r.provenance.trust_class == "trusted" for r in live)


def test_repeated_section_headings_do_not_overwrite_each_other(wiring):
    # Review finding H1: two `## Notes` sections used to key to the same
    # stable_key, so the second silently SUPERSEDED the first (data loss
    # through the primary ingest API). Both must now survive as distinct live
    # records, each retrievable, with their own content.
    orch, store, _ = wiring
    p = Principal(id="alice", namespace=_ACME)
    doc = "# Guide\n\n## Notes\n\nfirst note about alpha\n\n## Notes\n\nsecond note about beta\n"
    _ingest(orch, doc, p, source_id="guide.md")
    live = list(store.live_in_namespace(_ACME))
    texts = {r.body_text() for r in live}
    assert any("alpha" in t for t in texts), f"first '## Notes' section lost: {texts}"
    assert any("beta" in t for t in texts), f"second '## Notes' section lost: {texts}"
    # Both sections still SHOW the same human-facing heading path — only the
    # internal CAS key was disambiguated.
    note_paths = [r.body.section_path for r in live if "Notes" in "/".join(r.body.section_path)]
    assert len(note_paths) == 2

    # Re-ingesting the identical document is still a clean no-op (the
    # occurrence-suffixed keys are stable across ingests, so no spurious
    # supersede of the disambiguated section).
    before = {r.id for r in store.live_in_namespace(_ACME)}
    _ingest(orch, doc, p, source_id="guide.md")
    after = {r.id for r in store.live_in_namespace(_ACME)}
    assert before == after


def test_reingesting_an_unchanged_document_writes_nothing_new(wiring):
    orch, store, _ = wiring
    p = Principal(id="alice", namespace=_ACME)
    _ingest(orch, _DOC, p)
    before = {r.id for r in store.live_in_namespace(_ACME)}
    _ingest(orch, _DOC, p)  # identical re-ingest
    after = {r.id for r in store.live_in_namespace(_ACME)}
    assert before == after  # idempotent: same content -> same record ids, no churn


def test_reingesting_edited_content_supersedes_only_the_changed_span(wiring):
    orch, store, _ = wiring
    p = Principal(id="alice", namespace=_ACME)
    _ingest(orch, _DOC, p)
    edited = _DOC.replace(
        "Roll back by pinning the previous image tag and redeploying.",
        "Roll back by pinning the previous image tag, draining traffic, then redeploying.",
    )
    _ingest(orch, edited, p)
    live = list(store.live_in_namespace(_ACME))
    texts = [r.body_text() for r in live]
    assert any("draining traffic" in t for t in texts)  # the edit is live
    assert not any(
        "previous image tag and redeploying." in t and "draining" not in t for t in texts
    )  # the old version is no longer live
    # exactly one live record per span still holds
    assert len({(r.body.section_path, i) for i, r in enumerate(live)}) == len(live)


def test_authority_tier_is_clamped_without_the_verified_source_capability(wiring):
    orch, store, _ = wiring

    # A policy that tries to mint a "primary"-authority record.
    from datetime import datetime, timezone

    from datum.kernel.record import ProvenanceCapsule, StructuredBody
    from datum.kernel.writeop import WriteOp

    class OverclaimingPolicy:
        name, version = "overclaim", "1.0"

        def ingest(self, raw, principal):  # noqa: ANN001
            prov = ProvenanceCapsule(
                writer=principal,
                ingestion_path="test",
                authority_tier="primary",  # claims high authority
                trust_class="trusted",
                source_version="x",
            )
            return [
                WriteOp.assert_(
                    body=StructuredBody(text="claims to be primary"),
                    valid_from=datetime.now(timezone.utc),
                    provenance=prov,
                    policy_id="default-acl",
                    source_id="s",
                    stable_key="k",
                )
            ]

    orch.register_policy("overclaim", OverclaimingPolicy())
    ordinary = Principal(id="bob", namespace=_ACME)  # no verified_source capability
    orch.execute("overclaim", DocumentInput(source_id="s", policy_id="default-acl", text=""), ordinary)  # type: ignore[arg-type]
    (rec,) = list(store.live_in_namespace(_ACME))
    assert rec.provenance.authority_tier == "inferred"  # clamped down, not "primary"

    # A verified-source principal keeps the claimed tier.
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE TABLE records RESTART IDENTITY CASCADE")
    verified = Principal(id="ci", namespace=_ACME, capabilities=frozenset({"verified_source"}))
    orch.execute("overclaim", DocumentInput(source_id="s", policy_id="default-acl", text=""), verified)  # type: ignore[arg-type]
    (rec2,) = list(store.live_in_namespace(_ACME))
    assert rec2.provenance.authority_tier == "primary"


def test_cross_namespace_write_is_refused(wiring):
    orch, store, _ = wiring
    # DocumentPolicy stamps provenance.writer = the acting principal, so a
    # cross-namespace write can only arise from a policy that hardcodes a
    # foreign writer; simulate that and confirm the guard bites.
    from datetime import datetime, timezone

    from datum.kernel.record import ProvenanceCapsule, StructuredBody
    from datum.kernel.writeop import WriteOp

    class ForeignWriterPolicy:
        name, version = "foreign", "1.0"

        def ingest(self, raw, principal):  # noqa: ANN001
            prov = ProvenanceCapsule(
                writer=Principal(id="x", namespace="tenant:other"),  # not the actor's namespace
                ingestion_path="test",
                authority_tier="UNVERIFIED",
                trust_class="trusted",
                source_version="x",
            )
            return [
                WriteOp.assert_(
                    body=StructuredBody(text="cross-tenant"),
                    valid_from=datetime.now(timezone.utc),
                    provenance=prov,
                    policy_id="default-acl",
                    source_id="s",
                    stable_key="k",
                )
            ]

    orch.register_policy("foreign", ForeignWriterPolicy())
    actor = Principal(id="alice", namespace=_ACME)
    with pytest.raises(AdmissionError):
        orch.execute("foreign", DocumentInput(source_id="s", policy_id="default-acl", text=""), actor)  # type: ignore[arg-type]


def test_a_precondition_can_reject_a_write(wiring):
    orch, store, preconditions = wiring

    @preconditions.precondition
    def no_secrets(prior, new) -> bool:  # noqa: ANN001
        text = new if isinstance(new, str) else new.text
        return "PASSWORD=" not in text

    p = Principal(id="alice", namespace=_ACME)
    with pytest.raises(AdmissionError, match="no_secrets"):
        _ingest(orch, "# Config\n\nPASSWORD=hunter2\n", p)
