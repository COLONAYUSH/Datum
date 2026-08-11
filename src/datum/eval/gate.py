"""The eval gate, wired to the real Corpus (Milestone C).

`eval/regression.py` defines the fixed, human-curated regression set and a
generic `(query, namespace) -> Evidence` seam (`EvidenceFn`) so the pass/fail
logic can be unit-tested against a fake. This module closes that seam onto the
REAL system: it ingests the bundled sample corpus into a live `Corpus`
(dense + BM25 + ANN through the conformance gate), binds `evidence_fn` to
`corpus.search`, and runs the fixed set. A regression in any config the plan
compiler, the policy rule table, the fusion weights, the embedder, an operator
now fails the gate against real retrieval, which is what "a small fixed set
gates any manual config change" (FRAMEWORK.md §MVP definition, Eval) means in
practice.

The gate is the pytest integration test (`tests/eval/test_gate_integration.py`)
and the `datum eval` CLI, both calling `run_gate` here. Neither invents cases
or scores; the human-authored fixture is the whole specification, exactly as
regression.py's docstring insists.

**Side effect, stated plainly:** `run_gate` INGESTS the sample corpus into the
`Corpus` it is handed, under the namespaces the fixture names (`eng`/`hr`,
derived from each fixture file's name prefix). Point it at a scratch database,
never one holding real content — the same TEST-SAFETY discipline the DB-backed
test suite follows.
"""

from __future__ import annotations

from pathlib import Path

from datum.corpus import Corpus
from datum.eval.regression import EvidenceFn, RegressionReport, load_regression_set, run_regression
from datum.kernel.principal import Principal

# Repo-relative defaults: the fixture corpus and regression set are dev/CI
# artifacts (they live under tests/fixtures), so the defaults resolve from this
# module's own location rather than assuming a shipped-package data path. A
# caller in a different layout passes explicit paths.
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CORPUS_DIR = _REPO_ROOT / "tests" / "fixtures" / "sample_corpus"
DEFAULT_REGRESSION_SET = _REPO_ROOT / "tests" / "fixtures" / "regression_set.yaml"

# The abstention floor CALIBRATED FOR THIS FIXTURE CORPUS (decisions.md #34).
# The sample corpus is small and homogeneous (workplace policy docs), so its
# genuine-match dense-cosine scale sits high (~0.53–0.75) and its
# out-of-corpus / cross-namespace queries at ~0.33–0.50; a floor of 0.53
# separates them. This is per-corpus calibration of a documented knob — the
# regression-set oracle (the expected answers) is untouched — exactly the
# per-deployment tuning the configurable floor exists for. A diverse corpus
# uses the lower recall-biased default instead.
GATE_ABSTAIN_FLOOR = 0.53


def _namespace_for(path: Path) -> str:
    """The fixture convention: a file's namespace is its name prefix before
    the first underscore (`eng_api_deprecation.md` -> `eng`). The regression
    set's `principal_namespace` fields are written against exactly this.
    """
    prefix = path.stem.split("_", 1)[0]
    if not prefix:
        raise ValueError(
            f"fixture file {path.name!r} has no namespace prefix; expected "
            "`<namespace>_<name>.md` (e.g. eng_incident_response.md)."
        )
    return prefix


def ingest_sample_corpus(corpus: Corpus, corpus_dir: Path = DEFAULT_CORPUS_DIR) -> int:
    """Ingest every `*.md` under `corpus_dir` into `corpus`, each under the
    namespace its filename prefix names. Returns the file count ingested.
    """
    files = sorted(corpus_dir.glob("*.md"))
    if not files:
        raise FileNotFoundError(f"no *.md fixture files under {corpus_dir!r}")
    for path in files:
        namespace = _namespace_for(path)
        corpus.ingest(
            path.stem,
            path.read_text(encoding="utf-8"),
            principal=Principal(id="eval-ingestor", namespace=namespace),
        )
    return len(files)


def evidence_fn_for(corpus: Corpus) -> EvidenceFn:
    """Bind the generic regression seam to a live Corpus: each case's
    (query, namespace) becomes a real `corpus.search` as a principal in that
    namespace.
    """

    def evidence_fn(query: str, namespace: str):
        return corpus.search(query, principal=Principal(id="eval", namespace=namespace))

    return evidence_fn


def run_gate(
    corpus: Corpus,
    *,
    corpus_dir: Path = DEFAULT_CORPUS_DIR,
    regression_set: Path = DEFAULT_REGRESSION_SET,
) -> RegressionReport:
    """Ingest the fixture corpus into `corpus`, then run the fixed regression
    set against real retrieval. See the module docstring's side-effect note.
    """
    ingest_sample_corpus(corpus, corpus_dir)
    cases = load_regression_set(str(regression_set))
    return run_regression(cases, evidence_fn_for(corpus))
