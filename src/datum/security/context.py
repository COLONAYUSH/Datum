"""Ambient resolution of "who is calling right now."

FRAMEWORK.md §Core abstractions #7 specifies this mechanism directly, in
response to a coverage-audit finding that `search()`'s signature (no explicit
`principal` parameter, unlike `navigate`/`fetch`) read as an unexplained
exception to axiom 4's "does not compile without a value":

    `current_principal()` reads a request-scoped context populated exactly
    once, at MCP session/connection time, by the deployment's own auth
    middleware (the bearer token, mTLS identity, or session cookie the
    transport layer already validated) — never from a tool-call argument,
    and never from anything a model supplies. [...] `current_principal()`
    failing to resolve (no session context populated) raises, rather than
    defaulting to `None` or an anonymous/admin principal, so an
    unauthenticated call fails closed at exactly this seam rather than
    silently proceeding.

That "never from a tool-call argument" clause is the actual security property:
accepting a model-supplied principal would be a prompt-injectable escalation
path (a planted document could instruct the model to call a tool with an
elevated principal). `bind_principal` is therefore called exactly once per
session, by trusted server-side middleware — never by request-handling code
that has seen model or tool-call input — and every retrieval call downstream
reads the ambient value via `current_principal()` rather than accepting one
as a parameter.

A `contextvars.ContextVar` (not a plain module global) is used specifically
because MCP sessions are handled concurrently — often on asyncio tasks, and
CI-05's own "does not compile without a value" guarantee would be worthless
if one session's principal could leak into another's concurrent call via a
shared mutable global. `ContextVar` gives each asyncio task (and each thread,
since a copied context also propagates across threads started with
`contextvars.copy_context()`) an isolated view, and `bind_principal`'s
token-based reset restores exactly the value that was ambient before the
`with` block, even under nesting.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from datum.kernel.errors import PrincipalResolutionError
from datum.kernel.principal import Principal

_current_principal: ContextVar[Principal | None] = ContextVar(
    "datum_current_principal", default=None
)


def current_principal() -> Principal:
    """Return the `Principal` bound to the current call context.

    Raises `PrincipalResolutionError` — never returns `None` and never
    fabricates an anonymous or admin identity — when no principal has been
    bound. This is CI-05's enforcement point: "no default principal, ever."
    A caller reaching this function outside a `bind_principal` block (e.g. a
    background job or a test that forgot to set one up) is a bug to surface
    immediately, not a case to paper over with a convenient default.
    """
    principal = _current_principal.get()
    if principal is None:
        raise PrincipalResolutionError(
            "No principal is bound to the current call context. "
            "current_principal() never returns a default/anonymous identity — "
            "the caller (typically auth middleware at MCP session/connection "
            "time) must call bind_principal() first."
        )
    return principal


@contextmanager
def bind_principal(principal: Principal) -> Iterator[None]:
    """Bind `principal` as the ambient current principal for the `with` block.

    Intended caller: auth middleware, exactly once per MCP session/connection,
    after it has already validated the bearer token / mTLS identity / session
    cookie itself — never request-handling code acting on model or tool-call
    input (see module docstring). The previous value (`None` if nothing was
    bound, or an outer principal under legitimate nesting — e.g. a scoped
    internal call running as a service principal within a user's session) is
    restored on exit via the `ContextVar` reset token, including when the
    block raises.
    """
    token = _current_principal.set(principal)
    try:
        yield
    finally:
        _current_principal.reset(token)
