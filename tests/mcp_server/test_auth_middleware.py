"""Proves auth_middleware's connection-time seam: `authenticated_session`
binds `datum.security.context`'s ambient principal for exactly the lifetime
of its `with` block, via `StaticPrincipalResolver`'s dev-only stand-in.
"""

from __future__ import annotations

import pytest

from datum.kernel.errors import PrincipalResolutionError
from datum.kernel.principal import Principal
from datum.mcp_server.auth_middleware import StaticPrincipalResolver, authenticated_session
from datum.security.context import current_principal

ALICE = Principal(id="alice", namespace="tenant:acme")


def test_current_principal_raises_before_any_session_starts() -> None:
    with pytest.raises(PrincipalResolutionError):
        current_principal()


def test_authenticated_session_binds_the_resolved_principal() -> None:
    resolver = StaticPrincipalResolver(ALICE)
    with authenticated_session("any-bearer-token", resolver) as principal:
        assert principal is ALICE
        assert current_principal() is ALICE


def test_authenticated_session_unbinds_after_the_block() -> None:
    resolver = StaticPrincipalResolver(ALICE)
    with authenticated_session("any-bearer-token", resolver):
        pass
    with pytest.raises(PrincipalResolutionError):
        current_principal()


def test_static_resolver_ignores_the_credential_value() -> None:
    resolver = StaticPrincipalResolver(ALICE)
    assert resolver.resolve("literally anything") is ALICE
    assert resolver.resolve("") is ALICE
