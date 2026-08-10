"""Proves CI-05's "no default principal, ever" property for
datum.security.context: current_principal() raises with nothing bound,
resolves to the bound principal inside a `with bind_principal(...)` block,
and restores the prior ambient state (including "nothing bound") on exit —
even when the block raises.
"""

from __future__ import annotations

import pytest

from datum.kernel.errors import PrincipalResolutionError
from datum.kernel.principal import Principal
from datum.security.context import bind_principal, current_principal

ALICE = Principal(id="alice", namespace="tenant:acme")
BOB = Principal(id="bob", namespace="tenant:acme:finance")


def test_current_principal_raises_when_unbound() -> None:
    with pytest.raises(PrincipalResolutionError):
        current_principal()


def test_bind_principal_resolves_inside_the_block() -> None:
    with bind_principal(ALICE):
        assert current_principal() is ALICE


def test_bind_principal_restores_unbound_state_after_the_block() -> None:
    with bind_principal(ALICE):
        pass
    with pytest.raises(PrincipalResolutionError):
        current_principal()


def test_bind_principal_restores_outer_principal_after_nested_block() -> None:
    with bind_principal(ALICE):
        assert current_principal() is ALICE
        with bind_principal(BOB):
            assert current_principal() is BOB
        assert current_principal() is ALICE
    with pytest.raises(PrincipalResolutionError):
        current_principal()


def test_bind_principal_restores_prior_state_even_if_block_raises() -> None:
    class Boom(Exception):
        pass

    with pytest.raises(Boom):
        with bind_principal(ALICE):
            assert current_principal() is ALICE
            raise Boom()

    with pytest.raises(PrincipalResolutionError):
        current_principal()
