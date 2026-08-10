"""Auth middleware: binds `datum.security.context`'s ambient principal once,
at MCP session/connection time, from whatever the transport already
validated (bearer token, mTLS identity, session cookie) — never from a
tool-call argument, per FRAMEWORK.md §Core abstractions #7 (see
`datum.security.context`'s own module docstring for the full argument).

This module owns none of the actual resolution logic: `current_principal`/
`bind_principal` live in `datum.security.context` (built as this project's
security layer, out of this module's scope). What this module adds is the
*connection-time seam* — a pluggable `PrincipalResolver` a deployment plugs
its real auth backend into, plus one context manager that resolves a raw
credential and binds the result for the duration of a session, so no
request-handling code downstream (which has, by definition, already seen
whatever a model or a planted document put in its arguments) is ever in a
position to choose or influence which principal is bound.

`StaticPrincipalResolver` below is the *only* implementation this module
ships: it accepts a fixed `Principal` regardless of the credential offered,
for local dev and tests. It is not, and is not trying to be, an auth
backend — a deployment wires a real `PrincipalResolver` (validating a JWT,
looking up an mTLS certificate against an identity provider, checking a
session store) against the same Protocol before going anywhere near
production traffic.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Protocol, runtime_checkable

from datum.kernel.principal import Principal
from datum.security.context import bind_principal


@runtime_checkable
class PrincipalResolver(Protocol):
    """What connection-time auth middleware needs from an auth backend:
    turn whatever credential the transport already validated into a
    `Principal`. Deliberately the only method on this Protocol — resolution
    (checking a signature, calling an identity provider) is the backend's
    job; binding the result into the ambient context is this module's job,
    and the two are kept separate so a `PrincipalResolver` implementation
    never needs to know `datum.security.context` exists.
    """

    def resolve(self, raw_credential: str) -> Principal:
        """Turn a raw bearer token / session identifier into a `Principal`.

        Implementations should raise (not return a sentinel) on an invalid
        or expired credential — `authenticated_session` below does not
        catch resolution errors, so a caller sees the real failure rather
        than a principal that silently resolved to nothing.
        """
        ...


class StaticPrincipalResolver:
    """Dev/test-only `PrincipalResolver`: every `raw_credential` resolves to
    the same fixed `Principal`, regardless of its value.

    This is a stand-in for local development and the test suite, not a
    production auth system — it does not check the credential at all, which
    is exactly the property that makes it useless as anything else. A real
    deployment's `PrincipalResolver` must actually validate `raw_credential`
    (verify a JWT signature, look up a session, check an mTLS cert chain)
    before this module's fail-closed guarantee (an unauthenticated call
    raises rather than silently proceeding, per `security.context`'s own
    docstring) means anything.
    """

    def __init__(self, principal: Principal) -> None:
        self._principal = principal

    def resolve(self, raw_credential: str) -> Principal:  # noqa: ARG002 - dev stand-in, credential unused by design
        return self._principal


@contextmanager
def authenticated_session(raw_credential: str, resolver: PrincipalResolver) -> Iterator[Principal]:
    """Resolve `raw_credential` via `resolver` and bind the result as the
    ambient principal for the lifetime of the `with` block — the connection-
    time seam FRAMEWORK.md §Core abstractions #7 specifies.

    Intended call site: once per MCP session, immediately after the
    transport layer has validated the underlying credential and handed this
    middleware the resulting token/identity string, before any tool-call
    dispatch happens. `resolver.resolve()` is called *before* `bind_principal`
    so a resolution failure (bad token, expired session) raises before
    anything is bound — there is no window where a partially-authenticated
    session has a principal ambient. Outside this block (before it starts or
    after it exits), `datum.security.context.current_principal()` raises
    `PrincipalResolutionError`, per that module's fail-closed default: this
    context manager binds for the session's lifetime, never longer.
    """
    principal = resolver.resolve(raw_credential)
    with bind_principal(principal):
        yield principal
