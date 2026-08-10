"""Write-time preconditions: caller-registered checks that can reject a write
before it commits.

Backs FRAMEWORK.md §Core abstractions #1's `@corpus.precondition` example —
the reject-destructive-composition hook, whose canonical case is the Haystack
`#8491` class (a default cleaner strips the delimiter its own chunker needs,
silently collapsing a document to one chunk). A precondition sees the prior
live record for a span (or None on a first write) and the proposed new one,
and returns True to allow or False to reject; a rejection becomes an
`AdmissionError` at the write boundary rather than a silently-accepted
corruption.

This is the registry and evaluation logic. The write path (L3
WriteOrchestrator) is what actually calls `evaluate()` before dispatching an
op to the ground store; wiring is done there so the store stays a pure
persistence layer and the policy of *which* preconditions apply lives with
the orchestrator that admits writes.
"""

from __future__ import annotations

from collections.abc import Callable

from datum.kernel.errors import AdmissionError
from datum.kernel.record import Record, StructuredBody

# A precondition: given the prior live record for a span (or None) and the
# proposed new body, return True to allow the write, False to reject it.
Precondition = Callable[[Record | None, "str | StructuredBody"], bool]


class PreconditionRegistry:
    """Holds registered preconditions and evaluates them against a proposed
    write. Registration is via `register` or the `precondition` decorator so
    a caller can write `@registry.precondition` exactly as the spec's
    `@corpus.precondition` example shows (Corpus delegates to an instance of
    this at composition time).
    """

    def __init__(self) -> None:
        self._checks: list[tuple[str, Precondition]] = []

    def register(self, check: Precondition, *, name: str | None = None) -> Precondition:
        self._checks.append((name or getattr(check, "__name__", "precondition"), check))
        return check

    def precondition(self, check: Precondition) -> Precondition:
        """Decorator form: `@registry.precondition` registers `check` and
        returns it unchanged, so the decorated name stays callable/testable
        on its own.
        """
        return self.register(check)

    def evaluate(self, prior: Record | None, new_body: str | StructuredBody) -> None:
        """Run every registered precondition; raise `AdmissionError` naming
        the first that rejects. No checks registered means every write is
        allowed (the v1 default — preconditions are opt-in, not a gate a
        deployment must populate before it can write).
        """
        for name, check in self._checks:
            try:
                allowed = check(prior, new_body)
            except Exception as exc:
                # A precondition that raises is treated as a rejection, not a
                # pass-through: an admission check that can be made to throw
                # must fail closed, exactly like the ACL layer (security/acl).
                raise AdmissionError(
                    f"precondition {name!r} raised while evaluating a write; "
                    f"treating as rejection (fail closed): {exc!r}"
                ) from exc
            if not allowed:
                raise AdmissionError(f"write rejected by precondition {name!r}.")
