"""Principal: the identity a retrieval or write call runs on behalf of.

There is no default principal anywhere in this codebase. security.context
raises PrincipalResolutionError when none is set for the current call, rather
than falling back to an "anonymous" or "admin" identity — the single
requirement this whole layer exists to satisfy (CI-05: retrieval must not be
able to run without a principal, on pain of an exception, not a guess).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Principal:
    id: str
    namespace: str  # the coarse ACL dimension: tenant/department, evaluated first
    capabilities: frozenset[str] = field(default_factory=frozenset)

    def has_capability(self, name: str) -> bool:
        return name in self.capabilities
