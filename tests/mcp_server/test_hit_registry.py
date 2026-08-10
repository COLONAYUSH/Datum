"""Proves HitRegistry's stateless HMAC scheme: a clean issue/resolve
round-trip, tamper detection collapsing every failure mode (flipped payload
byte, flipped signature byte, a token from a different key, outright
garbage) to the same `HitIntegrityError`, and the loud dev-default warning
firing when `DATUM_HIT_SIGNING_KEY` is unset.

The token carries only a reference (content_ref + version), never a trust
judgment — see hit_registry.py's module docstring and decisions.md #12 for
why that boundary is the point. `test_token_carries_no_trust_metadata` below
is the regression test for the review finding that first-draft tokens
embedded `trust_tier`/`authority_tier` in base64-recoverable plaintext.

Deliberately absent: any assertion that a `hit_id` is confidential. It is
tamper-evident, not secret (hmac/hashlib give integrity, not secrecy); the
payload is base64-recoverable by design. The security property is that what
is recoverable is only a reference the caller already holds, not a trust
label — which is exactly what `test_token_carries_no_trust_metadata` checks.
"""

from __future__ import annotations

import base64
import json

import pytest

from datum.mcp_server.hit_registry import HitIntegrityError, HitRegistry


@pytest.fixture
def registry() -> HitRegistry:
    # Explicit key: these tests are about the scheme's correctness, not
    # about which key a bare `HitRegistry()` happens to pick up.
    return HitRegistry(signing_key=b"test-signing-key-not-for-prod")


def test_issue_returns_a_single_opaque_string_token(registry: HitRegistry) -> None:
    hit_id = registry.issue("doc://contracts/acme.md#118-134", version="snap-1")
    assert isinstance(hit_id, str)
    assert hit_id.count(".") == 1


def test_resolve_round_trips_the_reference(registry: HitRegistry) -> None:
    hit_id = registry.issue("doc://contracts/acme.md#118-134", version="snap-1")
    resolved = registry.resolve(hit_id)
    assert resolved["content_ref"] == "doc://contracts/acme.md#118-134"
    assert resolved["version"] == "snap-1"
    assert "issued_at" in resolved


def test_token_carries_no_trust_metadata(registry: HitRegistry) -> None:
    """Regression for the reviewed defect: a model that base64-decodes its own
    hit_id must recover only a reference, never a trust/authority judgment.
    We decode the payload WITHOUT the signing key (exactly what an adversary
    or a prompt-injected model can do) and assert no trust field is present.
    """
    hit_id = registry.issue("doc://contracts/acme.md#118-134", version="snap-1")
    payload_part = hit_id.split(".")[0]
    padding = "=" * (-len(payload_part) % 4)
    decoded = json.loads(base64.urlsafe_b64decode(payload_part + padding))
    assert set(decoded) == {"content_ref", "version", "issued_at", "nonce"}
    for forbidden in ("trust_tier", "authority_tier", "trust_class", "verdict"):
        assert forbidden not in decoded


def test_two_issues_of_the_same_reference_mint_different_hit_ids(registry: HitRegistry) -> None:
    a = registry.issue("ref", version="snap-1")
    b = registry.issue("ref", version="snap-1")
    assert a != b


def test_resolve_rejects_a_flipped_payload_byte(registry: HitRegistry) -> None:
    hit_id = registry.issue("ref", version="snap-1")
    payload_part, signature_part = hit_id.split(".")
    tampered_char = "A" if payload_part[0] != "A" else "B"
    tampered = tampered_char + payload_part[1:] + "." + signature_part
    with pytest.raises(HitIntegrityError):
        registry.resolve(tampered)


def test_resolve_rejects_a_flipped_signature_byte(registry: HitRegistry) -> None:
    hit_id = registry.issue("ref", version="snap-1")
    payload_part, signature_part = hit_id.split(".")
    tampered_char = "A" if signature_part[0] != "A" else "B"
    tampered = payload_part + "." + tampered_char + signature_part[1:]
    with pytest.raises(HitIntegrityError):
        registry.resolve(tampered)


def test_resolve_rejects_total_garbage(registry: HitRegistry) -> None:
    with pytest.raises(HitIntegrityError):
        registry.resolve("not-a-real-hit-id-at-all")


def test_resolve_rejects_a_token_issued_by_a_different_key() -> None:
    a = HitRegistry(signing_key=b"key-one")
    b = HitRegistry(signing_key=b"key-two")
    hit_id = a.issue("ref", version="snap-1")
    with pytest.raises(HitIntegrityError):
        b.resolve(hit_id)


def test_unset_signing_key_warns_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    import datum.mcp_server.hit_registry as hit_registry_module

    monkeypatch.delenv("DATUM_HIT_SIGNING_KEY", raising=False)
    hit_registry_module._process_default_signing_key.cache_clear()

    registry = HitRegistry()
    with pytest.warns(RuntimeWarning, match="DATUM_HIT_SIGNING_KEY"):
        hit_id = registry.issue("ref", version="snap-1")
    resolved = registry.resolve(hit_id)
    assert resolved["content_ref"] == "ref"

    hit_registry_module._process_default_signing_key.cache_clear()
