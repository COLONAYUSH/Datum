"""View: lineage-tracked, budgeted, incrementally maintained derivation (L4).

v1 ships exactly two Views (built in derivation.views.lexical and
derivation.views.dense) — a lexical BM25-shaped view and one dense embedding
view. Both are deterministic, local-compute derivations with no LLM call
inside them, so `refresh_budget`/`staleness_sla` are optional here and unused
by either v1 View builder.

PromptArtifact (a versioned, diffable LLM-prompt-as-derivation-input type,
for a future enrichment View like contextual-header generation) is a
pre-budgeted kernel symbol per FRAMEWORK.md's kernel symbol budget, but is
deliberately NOT defined here as a class: v1 has no LLM-mediated View to
register one against, and a stub class with no consumer is worse than an
honest gap. See datum/__init__.py's deferred-symbol comment table.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from datum.kernel.plan import Budget


@dataclass(frozen=True)
class View:
    name: str
    inputs: tuple[str, ...]
    producer_version: str
    refresh_budget: Budget | None = None
    staleness_sla: str | None = None
    prompt_version: str | None = None  # set only once a PromptArtifact-consuming view exists
    extra: dict[str, str] = field(default_factory=dict)
