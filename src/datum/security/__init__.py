"""datum.security: cross-cutting principal resolution and namespace ACL.

Two independent concerns live here, both load-bearing for CI-05 ("authorization
as a paid tier, not a primitive" — FRAMEWORK.md §Issue-coverage traceability):

- `context`: the ambient-resolution mechanism for "who is calling right now."
  There is no default principal anywhere in this codebase; `current_principal()`
  raises rather than guessing (FRAMEWORK.md §Core abstractions #7).
- `acl`: v1's authorization mechanism, namespace partitioning on the coarse
  tenant/department dimension (FRAMEWORK.md §MVP definition — "ACL ships as
  namespace partitioning on the tenant/department dimension only" at v1; the
  fine-grained conformance-tested-predicate path is Phase 1, not built here).

Neither module is part of the budgeted kernel surface (datum/__init__.py's
`__all__`) — they are internal plumbing the writepath/planner/mcp_server
layers call, not agent-facing types.
"""
