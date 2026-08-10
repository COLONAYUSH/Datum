"""Proves the v1 namespace-partition ACL (datum.security.acl): exact-equality
grant only (no subtree/prefix hierarchy — decisions.md #13), denial for every
non-equal namespace including former "subtree" cases, and the fail-closed
contract require_namespace_access exists to guarantee — it denies rather than
raising past the boundary when the underlying check, the principal, or the
record namespace itself blows up.
"""

from __future__ import annotations

import pytest

from datum.kernel.errors import AdmissionError
from datum.kernel.principal import Principal
from datum.security import acl

TENANT_ACME = Principal(id="svc", namespace="tenant:acme")
ACME_FINANCE = Principal(id="alice", namespace="tenant:acme:finance")
TENANT_ACME2 = Principal(id="mallory", namespace="tenant:acme2")


def test_exact_namespace_match_is_allowed() -> None:
    assert acl.check_namespace_access(ACME_FINANCE, "tenant:acme:finance") is True


def test_coarse_principal_does_not_reach_a_sub_namespace_at_v1() -> None:
    # v1 is exact-equality only: a subtree grant is Phase 1 (decisions.md #13),
    # precisely so the ACL never grants more than the storage equality filter
    # can honor. `tenant:acme` reaches ONLY `tenant:acme`.
    assert acl.check_namespace_access(TENANT_ACME, "tenant:acme:finance") is False
    assert acl.check_namespace_access(TENANT_ACME, "tenant:acme:legal") is False
    assert acl.check_namespace_access(TENANT_ACME, "tenant:acme") is True


def test_department_scoped_principal_cannot_reach_sibling_or_parent() -> None:
    assert acl.check_namespace_access(ACME_FINANCE, "tenant:acme:legal") is False
    assert acl.check_namespace_access(ACME_FINANCE, "tenant:acme") is False


def test_cross_tenant_access_is_denied() -> None:
    assert acl.check_namespace_access(TENANT_ACME, "tenant:other") is False


def test_no_substring_or_prefix_confusion() -> None:
    # The classic CI-03 trap: a prefix/substring check would let tenant:acme
    # leak into tenant:acme2. Exact-equality can't, by construction — assert it.
    assert acl.check_namespace_access(TENANT_ACME, "tenant:acme2") is False
    assert acl.check_namespace_access(TENANT_ACME, "tenant:acme2:finance") is False
    assert acl.check_namespace_access(TENANT_ACME2, "tenant:acme") is False


def test_require_namespace_access_passes_through_on_grant() -> None:
    acl.require_namespace_access(ACME_FINANCE, "tenant:acme:finance")  # no raise


def test_require_namespace_access_raises_admission_error_on_denial() -> None:
    with pytest.raises(AdmissionError):
        acl.require_namespace_access(ACME_FINANCE, "tenant:acme:legal")


def test_require_namespace_access_fails_closed_when_check_raises(monkeypatch) -> None:
    def boom(_principal: Principal, _record_namespace: str) -> bool:
        raise RuntimeError("simulated failure evaluating the ACL check")

    monkeypatch.setattr(acl, "check_namespace_access", boom)

    with pytest.raises(AdmissionError):
        acl.require_namespace_access(ACME_FINANCE, "tenant:acme:finance")


def test_check_namespace_access_itself_fails_closed_on_malformed_input() -> None:
    assert acl.check_namespace_access(ACME_FINANCE, 12345) is False  # type: ignore[arg-type]


def test_require_namespace_access_raises_admission_error_on_broken_principal() -> None:
    class ExplodingPrincipal:
        @property
        def id(self) -> str:
            raise RuntimeError("simulated broken principal")

        @property
        def namespace(self) -> str:
            raise RuntimeError("simulated broken principal")

    with pytest.raises(AdmissionError):
        acl.require_namespace_access(ExplodingPrincipal(), "tenant:acme:finance")  # type: ignore[arg-type]


def test_require_namespace_access_raises_admission_error_on_broken_record_namespace() -> None:
    # Finding 12: the record_namespace repr in the denial message must be
    # guarded too, not just the principal half. A namespace object whose
    # __repr__ raises must still surface as AdmissionError (access is denied
    # either way — this is about the exception TYPE, not the decision).
    class ReprBomb:
        def __repr__(self) -> str:
            raise RuntimeError("boom repr")

    with pytest.raises(AdmissionError):
        acl.require_namespace_access(ACME_FINANCE, ReprBomb())  # type: ignore[arg-type]
