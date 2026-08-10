"""HitRegistry: the out-of-band envelope store behind every opaque `hit_id`.

FRAMEWORK.md's hot-path budget table (§Subsystems, Query & planning) names two
storage strategies and requires a deployment to pick one, not discover the gap
in production:

1. A replicated key-value tier (TTL'd, cross-replica) — the production default,
   because it stays revocable: forgetting a record can also evict its envelope.
2. A **stateless** fallback: "an HMAC-signed token encoding `record_id`+snapshot
   version, decodable without shared state" (FRAMEWORK.md hot-path table,
   verbatim). It trades revocability (a token for a since-forgotten record stays
   decodable until the signing key or version rotates) for zero shared-state
   cost — the right trade for a single-replica/edge deployment, or, as here, a
   scaffold with no cache tier wired up yet.

This module implements (2), the MVP default. Swapping in (1) later means a
`RedisHitRegistry` (or similar) behind the same `issue`/`resolve` shape.

**What the token carries, and what it deliberately does NOT.** Per the spec
line above, the token encodes only a *reference* — `content_ref` plus a
`version` (a corpus/snapshot version) and an `issued_at` — never `trust_tier`,
`authority_tier`, or any trust judgment. This is the fix for a real defect an
adversarial review reproduced in the first draft of this file: `hmac`/`hashlib`
give integrity, not secrecy, so anything in the payload is base64-recoverable
by anyone (verifying the signature and reading the payload are separate steps;
only the former needs the key). An earlier draft embedded `trust_tier`/
`authority_tier` in the payload, which meant a model instructed to base64-decode
its own tool output could recover the exact trust metadata the out-of-band
envelope exists to keep away from it. Carrying only a reference closes that
channel by construction: decoding a `hit_id` reveals which record/span it points
at (which the caller is already retrieving — not a secret) and nothing about how
far that record is to be trusted.

Trust/authority resolution therefore happens SERVER-SIDE, at `resolve()` time,
by the layer that holds the records: whatever calls `resolve(hit_id)` gets back
the `content_ref`, looks the record up in the ground store, and reads
`trust_class`/`authority_tier` off the record's own `ProvenanceCapsule`. That
wiring lands with `Corpus` at Milestone A (the ground store does not exist yet);
this module is built and verified now so that future `Corpus` has a real,
spec-faithful token scheme to call. Recorded as decisions.md #12.

**Why not wired into `mcp_server.server` yet.** `search()`/`fetch()` in this
scaffold call an injected `corpus` returning kernel.surface types whose
`SearchHit`s already carry a `hit_id`. Minting those ids — calling `issue()` —
is the job of whatever populates that `Evidence`: a `FakeCorpus` in tests today,
`Corpus.search()` at Milestone A.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import warnings
from functools import lru_cache

from datum.kernel.errors import DatumError

_SIGNING_KEY_ENV_VAR = "DATUM_HIT_SIGNING_KEY"
_DIGEST = hashlib.sha256


class HitIntegrityError(DatumError):
    """Raised by `HitRegistry.resolve()` for any `hit_id` that does not
    verify: a flipped byte in the signature, a flipped byte in the payload,
    or outright garbage input (a non-base64 string, truncated token, or a
    hit_id minted by a registry running a different signing key).

    Deliberately a single exception type for all cases. Distinguishing "bad
    signature" from "malformed encoding" in the raised type would hand a
    caller probing hit_ids an oracle for which failure mode they hit — the
    opposite of what an opaque, tamper-evident token is for.
    """


@lru_cache(maxsize=1)
def _process_default_signing_key() -> bytes:
    """A random key generated once per process when `DATUM_HIT_SIGNING_KEY`
    is unset, cached so every no-arg `HitRegistry()` in this process shares
    it. Dev-only, and says so loudly: tokens minted before a process restart
    become permanently unresolvable after one. A real deployment sets
    `DATUM_HIT_SIGNING_KEY`, or runs the replicated-cache strategy instead.
    """
    warnings.warn(
        f"{_SIGNING_KEY_ENV_VAR} is unset. HitRegistry is generating a random "
        "signing key for this process only — hit_ids minted now will fail to "
        "resolve after a process restart or in any other process (a second "
        "replica, a fresh test process, etc). This is the dev default, not a "
        f"production posture: set {_SIGNING_KEY_ENV_VAR} to a stable, secret "
        "value before deploying.",
        category=RuntimeWarning,
        stacklevel=3,
    )
    return secrets.token_bytes(32)


def _signing_key() -> bytes:
    raw = os.environ.get(_SIGNING_KEY_ENV_VAR)
    if raw:
        return raw.encode("utf-8")
    return _process_default_signing_key()


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


class HitRegistry:
    """Mints and resolves opaque `hit_id` tokens via the stateless HMAC
    scheme. The token carries a *reference* (`content_ref` + `version` +
    `issued_at`), never a trust judgment — see the module docstring for why
    that boundary is load-bearing, not incidental.
    """

    def __init__(self, *, signing_key: bytes | None = None) -> None:
        """`signing_key` is normally left unset so this instance picks up the
        environment/process default lazily on first use (deferred, not read at
        import time, so importing this module never warns or generates key
        material). Passing one explicitly is for tests that need two
        registries to share, or deliberately not share, a key.
        """
        self._signing_key = signing_key

    def _key(self) -> bytes:
        return self._signing_key if self._signing_key is not None else _signing_key()

    def issue(self, content_ref: str, *, version: str) -> str:
        """Mint an opaque, tamper-evident `hit_id` encoding only a reference:
        `content_ref` (which record/span this points at) and `version` (the
        corpus/snapshot version it was resolved against, so a stale token is
        detectable once versions rotate). No trust/authority metadata is ever
        placed in the token — that is resolved server-side from the record
        itself (module docstring).

        A random per-call `nonce` makes two `issue()` calls for the identical
        `(content_ref, version)` mint different `hit_id`s, so "same hit_id"
        cannot be correlated across unrelated calls as a side channel.
        `issued_at` is a monotonic-ish mint timestamp for audit, not a
        security control.
        """
        payload = {
            "content_ref": content_ref,
            "version": version,
            "issued_at": _utc_now_iso(),
            "nonce": secrets.token_hex(8),
        }
        payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(self._key(), payload_bytes, _DIGEST).digest()
        return f"{_b64encode(payload_bytes)}.{_b64encode(signature)}"

    def resolve(self, hit_id: str) -> dict[str, str]:
        """Verify `hit_id`'s signature and return its decoded reference:
        `{"content_ref": ..., "version": ..., "issued_at": ..., "nonce": ...}`.
        The caller (the ground store / Corpus) uses `content_ref` to look up
        the record and read trust/authority off it — those never travel in
        the token.

        Raises `HitIntegrityError` — never a partial or best-effort result —
        for a tampered signature, a tampered payload, or a malformed/garbage
        token.
        """
        try:
            encoded_payload, encoded_signature = hit_id.split(".")
            payload_bytes = _b64decode(encoded_payload)
            signature = _b64decode(encoded_signature)
        except (ValueError, binascii.Error) as exc:
            raise HitIntegrityError(f"Malformed hit_id: {hit_id!r}") from exc

        expected_signature = hmac.new(self._key(), payload_bytes, _DIGEST).digest()
        if not hmac.compare_digest(signature, expected_signature):
            raise HitIntegrityError("hit_id signature verification failed (tampered or foreign key).")

        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HitIntegrityError(f"hit_id payload did not decode as JSON: {hit_id!r}") from exc

        if not isinstance(payload, dict):
            raise HitIntegrityError(f"hit_id payload was not a JSON object: {hit_id!r}")
        return payload


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
