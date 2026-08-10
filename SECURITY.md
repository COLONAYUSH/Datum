# Security policy

## Reporting a vulnerability

Please do not open a public issue for a security problem. Use GitHub's private vulnerability reporting
on this repository (the **Security** tab, then **Report a vulnerability**), which opens a private
channel with the maintainer.

Include what you found, how to reproduce it, and the impact you expect. You will get an
acknowledgement, and a fix or a mitigation plan once the report is confirmed.

## Why security is treated as an architecture property here

Datum is built so that a retrieval mistake cannot quietly become a data-isolation mistake. A few of
the properties a report should assume and test against:

- **Tenant isolation fails closed.** The namespace partition is resolved before any operator runs. A
  result handle (`hit_id`) minted in one namespace never yields content in another.
- **No default identity.** A principal is never inferred. An unresolved principal raises rather than
  falling back to something permissive.
- **Operators are gated.** A physical operator cannot register until it passes a conformance suite
  that includes tenancy fail-closed and entitlement-staleness checks. This applies to first-party
  operators too.
- **Handles carry no trust.** A `hit_id` is a signed reference with no trust tier or authority in it.
  Server-side state stays server-side.
- **Everything is audited.** Every plan's trace is persisted, so `explain` and `replay` can
  reconstruct exactly what a retrieval did.

A convincing security report is one that shows any of these properties can be broken.

## Scope note

This is a pre-1.0 research framework. The threat model above is the intended posture, not a
certified guarantee. Reports that show a gap between the two are exactly what is useful.
