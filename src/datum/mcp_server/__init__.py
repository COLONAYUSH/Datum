"""datum.mcp_server: the Agent Tool Surface's transport layer (FRAMEWORK.md §7).

Three independent concerns live here:

- `hit_registry`: the stateless HMAC-signed `hit_id` scheme — the mechanism
  that keeps `trust_class`/`authority_tier`/provenance server-side, resolved
  only through an opaque reference a model never decodes. `HitRegistry` is
  part of FRAMEWORK.md's budgeted 35-symbol kernel surface (§Security &
  governance's symbol count); it is *not yet* re-exported from
  `datum/__init__.py` (see that file's own comment on lines 109-110, written
  before this module existed) — wiring that export is this build's
  responsibility to flag, not to do, since `datum/__init__.py` is out of
  this module's assigned scope.
- `server`: the five-tool MCP surface (`search`/`fetch`/`navigate`/`explain`/
  `since`) built against an injected, swappable `corpus`-shaped object.
- `auth_middleware`: a dev-only `PrincipalResolver` stand-in that binds
  `datum.security.context`'s ambient principal at connection time, in place
  of a real bearer-token/mTLS backend this build does not implement.

None of these three are part of the budgeted kernel surface themselves
(`HitRegistry` is counted in the budget but not re-exported at top level yet;
`server`/`auth_middleware`'s own types are internal transport plumbing) —
mirrors `datum.security.__init__`'s own note on the same distinction.
"""
