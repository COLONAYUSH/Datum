"""v1 authorization: namespace partitioning as exact-equality on a partition key.

FRAMEWORK.md's MVP definition makes this the *entire* ACL mechanism at v1 —
the fine-grained, conformance-tested-predicate path (role, trial phase, IRB
tier) is Phase 1, not built here:

    "Principal/policy/budget: enforced from v1 [...] ACL ships as namespace
    partitioning on the tenant/department dimension only; the fine-grained
    conformance-tested-predicate path (and its entitlement-staleness
    fail-closed test) is Phase 1." (§MVP definition)

    "filtering since()'s WAL tail by the caller's namespace is a cheap
    equality check on a partition key" (§MVP definition, on `since()`)

**Why exact-equality, not a namespace subtree/prefix grammar (decisions.md
#13).** An earlier draft of this module invented a `:`-delimited subtree
grammar in which `tenant:acme` also granted `tenant:acme:finance`,
`tenant:acme:legal`, and so on. An adversarial review reproduced the problem
that creates: the storage layer (storage/wal.py, and the ground store built
on it) filters a namespace partition by SQL *equality* — exactly as the spec
line above requires — so a subtree grant and an equality filter disagree. A
coarse `tenant:acme` principal granted three sub-namespaces by the ACL would
have the storage filter return only the one partition literally named
`tenant:acme`, silently starving the principal of records it is authorized
for (the low-privilege-recall failure §Security & governance says must never
be silent) — or, to avoid that, the storage filter would have to become a
prefix scan, putting string-prefix logic back on the retrieval hot path,
which is the CI-03 filter-as-ACL-bypass shape this layer exists to prevent.

v1 resolves the tension by having no hierarchy at all: a principal's
namespace and a record's namespace grant access iff they are the *same
string*. One partition per principal, one partition per record (a record's
namespace is its writer's namespace, decisions.md #7), equality end to end,
ACL and storage filter provably in agreement. Multi-level namespace grants
(a tenant admin spanning its departments) are a Phase 1 capability that
arrives together with the fine-grained predicate path and a namespace-*set*
representation the storage layer can turn into a safe `IN (...)` filter —
not a prefix match. Building the weaker, exactly-consistent thing now, rather
than the richer thing that disagrees with the layer beneath it, is the
honest v1.
"""

from __future__ import annotations

from datum.kernel.errors import AdmissionError
from datum.kernel.principal import Principal


def check_namespace_access(principal: Principal, record_namespace: str) -> bool:
    """Return whether `principal` may access a record in `record_namespace`.

    True iff `principal.namespace` equals `record_namespace` exactly (v1 has
    no namespace hierarchy — see the module docstring). Anything that
    prevents a clean evaluation — a non-string namespace on either side, or
    any other unexpected input — is treated as a denial rather than
    propagated: this function is itself one of the two fail-closed layers
    `require_namespace_access` relies on, and an ACL check that can be made to
    raise into a caller that treats "unknown" as "allowed" is exactly CI-05's
    "authorization as an afterthought" failure restated as a bug.
    """
    try:
        principal_namespace = principal.namespace
        if not isinstance(principal_namespace, str) or not isinstance(record_namespace, str):
            return False
        return principal_namespace == record_namespace
    except Exception:
        return False


def require_namespace_access(principal: Principal, record_namespace: str) -> None:
    """Raise `AdmissionError` unless `principal` may access `record_namespace`.

    Fails closed, not open: any exception raised while evaluating
    `check_namespace_access` is caught here and treated as a denial, exactly
    like a clean `False`. It never propagates past this boundary as some
    other exception type a caller might mishandle by defaulting to "allow."
    The contract every caller in the write/query path can rely on without
    re-deriving it: this function either returns (access granted) or raises
    `AdmissionError` (access denied) — there is no third outcome, including
    no other exception type.
    """
    try:
        allowed = check_namespace_access(principal, record_namespace)
    except Exception:
        allowed = False

    if allowed:
        return

    # Build the entire denial message defensively. A malformed `principal`
    # OR a malformed `record_namespace` (a non-str object whose __repr__
    # raises — an explicitly by-design input class, since check_ tolerates
    # and denies it) could otherwise make the f-string itself raise
    # AttributeError/RuntimeError, leaking past a caller's
    # `except AdmissionError:` handler. Both interpolated values are built
    # inside their own guards so the raise below uses only strings already
    # known to be safe — this closes the review finding that an earlier fix
    # guarded only the principal half, not `record_namespace`.
    try:
        principal_detail = f"Principal {principal.id!r} (namespace {principal.namespace!r})"
    except Exception:
        principal_detail = "Principal <unrepresentable>"
    try:
        target_detail = repr(record_namespace)
    except Exception:
        target_detail = "<unrepresentable namespace>"
    raise AdmissionError(f"{principal_detail} is not authorized for namespace {target_detail}.")
