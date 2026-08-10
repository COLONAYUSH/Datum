"""The v1 eval gate: a small, fixed, human-curated regression set.

FRAMEWORK.md's MVP definition, §Eval bullet, is explicit that this is a cut
*and replacement* of an earlier draft, not a placeholder for it: "A small,
fixed, human-curated regression set (tens to low-hundreds of query/expected-
evidence pairs) gates any manual config change at v1," in place of the
zero-label, corpus-derived golden-set bootstrap (Chroma-style generative
benchmarking) that is deferred to Phase 1 alongside the promotion-gate
machinery it feeds. There is no generative case-authoring, no judge model,
and no scoring rubric in this module on purpose — every case here was
written by a human who read the corpus, and that is the entire point of
shipping this instead of the fancier thing.

Two design decisions worth stating, since neither is spelled out by the
task shape alone:

1. **`min_sufficiency` is a floor, in one direction, always.** A case never
   asks "sufficiency must be *below* X" by overloading this field — see (2).
   `kernel.evidence.CalibratedScore` is explicit that v1's sufficiency score
   is `calibrated=False`, method `"uncalibrated-raw-v1"`: a raw, uncalibrated
   float is a poor basis for a second, inverted threshold direction on the
   same field, but a perfectly fine basis for "at least this much evidence
   showed up," which is the only claim `min_sufficiency` makes here.

2. **An empty `expected_content_substrings` tuple is not "no assertion" —
   it is the case's way of saying "the correct behavior here is to abstain."**
   Rather than invent a second threshold direction on the uncalibrated score
   to express "this should come back nearly empty," this runner keys the
   negative case on `EvidenceState`'s own typed `status` outcome:
   `insufficient_evidence` is a first-class result a plan can produce
   (kernel.evidence module docstring — "never a generation-time surprise"),
   so a case that expects abstention should assert on that enum, not on a
   score whose only calibration guarantee is that it has none. This also
   means a case with an out-of-namespace query (the right document exists,
   but not in a namespace this principal can see) and a case with a
   genuinely out-of-corpus query are both expressed the same way: empty
   substrings, and the runner expects `insufficient_evidence` either way.
   See `tests/fixtures/regression_set.yaml` for one of each.

**Scope, stated honestly.** This module checks exactly what the caller's
`evidence_fn` returns for a fixed list of queries — it can catch a
misrouted or starved query (case asks for namespace A, gets namespace B's
content, the expected substring is absent, the case fails) and a query that
should abstain but doesn't (or vice versa). It cannot measure *continuous*
low-privilege recall across the fine-grained predicate ACL path — that
measurement discipline is namespace-partition-only at v1 and its continuous
form is a Phase 1 item (FRAMEWORK.md §MVP definition, Principal/policy/budget
bullet), not something a tens-of-cases fixed set can stand in for.

This module has zero dependency on Corpus, the planner, or any operator —
by construction, since none of those exist yet. `evidence_fn` is the seam:
whoever wires retrieval up later passes a real
`Callable[[str, str], Evidence]` (query, namespace) -> Evidence; the tests
in `tests/eval/test_regression.py` pass a hand-written fake one to prove the
pass/fail logic itself, not any retrieval quality.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from datum.kernel import Evidence

EvidenceFn = Callable[[str, str], Evidence]
"""(query, principal_namespace) -> Evidence. Caller-supplied; see module docstring."""


@dataclass(frozen=True)
class RegressionCase:
    """One human-curated query/expected-evidence pair.

    Kept deliberately simple — substring containment against returned
    evidence content, not exact-match, since ranking order and exact
    wording can vary run to run without the case actually regressing.
    """

    query: str
    expected_content_substrings: tuple[str, ...]
    min_sufficiency: float
    principal_namespace: str


@dataclass(frozen=True)
class RegressionReport:
    """The gate's verdict: an overall pass/fail plus a per-case trail.

    `results` is a case, its pass/fail, and a human-readable detail string
    explaining *why* — this is what makes a failing CI run diagnosable from
    the report alone, without re-running the case by hand.
    """

    passed: bool
    results: tuple[tuple[RegressionCase, bool, str], ...]


def _parse_case(entry: dict[str, Any], index: int) -> RegressionCase:
    """Raises ValueError naming the offending case's index and missing key,
    rather than a bare KeyError, because this file's entire job is gating
    config changes and a hand-edited fixture with a typo deserves a message
    that says which of tens-to-low-hundreds of entries is broken.
    """
    missing = [
        key
        for key in ("query", "min_sufficiency", "principal_namespace")
        if key not in entry
    ]
    if missing:
        raise ValueError(
            f"regression case at index {index} is missing required field(s) "
            f"{missing!r}: {entry!r}"
        )

    # Guard against the classic fixture slip `expected_content_substrings:
    # "the phrase"` (a bare string instead of a one-element list). tuple() over
    # a str silently explodes it into per-character "substrings" — and since
    # almost any English answer contains every individual letter, the gate
    # would then pass vacuously against evidence that lacks the phrase
    # entirely, silently neutralizing exactly the config-change gate this
    # module exists to be. Reject it loudly, naming the case, in the same
    # spirit as the missing-field check above. (Reviewed finding 8.)
    raw_substrings = entry.get("expected_content_substrings", ())
    if isinstance(raw_substrings, (str, bytes)):
        raise ValueError(
            f"regression case at index {index}: expected_content_substrings must be a "
            f"list of strings, not a bare string {raw_substrings!r} — wrap a single "
            f"substring in a one-element list to avoid it being split per-character."
        )
    try:
        substrings = tuple(raw_substrings)
    except TypeError as exc:
        raise ValueError(
            f"regression case at index {index}: expected_content_substrings must be a "
            f"list of strings, got {type(raw_substrings).__name__} {raw_substrings!r}."
        ) from exc
    if not all(isinstance(s, str) for s in substrings):
        raise ValueError(
            f"regression case at index {index}: every entry in "
            f"expected_content_substrings must be a string, got {substrings!r}."
        )

    return RegressionCase(
        query=str(entry["query"]),
        expected_content_substrings=substrings,
        min_sufficiency=float(entry["min_sufficiency"]),
        principal_namespace=str(entry["principal_namespace"]),
    )


def load_regression_set(path: str) -> tuple[RegressionCase, ...]:
    """Reads a YAML (`.yaml`/`.yml`) or JSON (`.json`) file of cases.

    The file's top level must be a list of objects, each with `query`,
    `min_sufficiency`, `principal_namespace`, and an optional
    `expected_content_substrings` list (defaults to empty — see the module
    docstring on what an empty list means). YAML support is import-guarded
    rather than a hard dependency of this module: PyYAML lives in the `dev`
    extra (this is a test-fixture format, not a runtime-critical one for
    every install of the package), so the import happens lazily, only when
    a `.yaml`/`.yml` file is actually loaded.
    """
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")

    if file_path.suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "Loading a YAML regression set requires PyYAML. Install the "
                "'dev' extra (pip install -e '.[dev]') or provide a .json file "
                "instead."
            ) from exc
        raw = yaml.safe_load(text)
    elif file_path.suffix == ".json":
        raw = json.loads(text)
    else:
        raise ValueError(
            f"Unsupported regression set file extension {file_path.suffix!r} "
            f"for {path!r}; expected .yaml, .yml, or .json."
        )

    if not isinstance(raw, list):
        raise ValueError(
            f"Regression set file {path!r} must contain a top-level list of "
            f"cases, got {type(raw).__name__}."
        )

    return tuple(_parse_case(entry, index) for index, entry in enumerate(raw))


def _evaluate_case(case: RegressionCase, evidence: Evidence) -> tuple[bool, str]:
    """The one piece of actual logic in this module — see module docstring
    decisions (1) and (2) for why the two branches below diverge the way
    they do.
    """
    if case.expected_content_substrings:
        combined_content = "\n".join(hit.content for hit in evidence.hits)
        missing = tuple(s for s in case.expected_content_substrings if s not in combined_content)
        if missing:
            return False, f"missing expected substring(s): {missing!r}"
        if evidence.sufficiency < case.min_sufficiency:
            return False, (
                f"sufficiency {evidence.sufficiency!r} is below the required "
                f"minimum {case.min_sufficiency!r}"
            )
        return True, "all expected substrings present and sufficiency met"

    # Empty expected_content_substrings: this case expects abstention,
    # whether because the query is genuinely out-of-corpus or because the
    # right answer exists but not in a namespace this principal can see.
    if evidence.status != "insufficient_evidence":
        return False, (
            "expected status 'insufficient_evidence' (no expected_content_substrings "
            f"were given for this case), got {evidence.status!r}"
        )
    return True, "correctly abstained with insufficient_evidence"


def run_regression(
    cases: Sequence[RegressionCase],
    evidence_fn: EvidenceFn,
) -> RegressionReport:
    """Runs every case through `evidence_fn` and reports pass/fail.

    `evidence_fn` is generic on purpose (see module docstring) — this
    function has no idea whether it is calling a fake, a walking-skeleton
    grep operator, or a fully compiled Plan; it only knows the (query,
    namespace) -> Evidence contract every future wiring must honor.
    """
    results = tuple(
        (case, *_evaluate_case(case, evidence_fn(case.query, case.principal_namespace)))
        for case in cases
    )
    passed = all(ok for _, ok, _ in results)
    return RegressionReport(passed=passed, results=results)
