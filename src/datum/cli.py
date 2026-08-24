"""The `datum` console entry point.

The subcommands each drive the real `Corpus` composition root (the same
object the MCP server exposes):

    datum ingest <path> --source-id ID --namespace NS   ingest a document
    datum search "<query>" --namespace NS                run a retrieval
    datum serve --namespace NS                            run the MCP server (stdio)
    datum eval [--corpus-dir D --regression-set F]       run the eval gate (Milestone C)
    datum benchmark                                       run the multi-format benchmark (task #30)

`--dsn` (or DATUM_PG_DSN) points at Postgres; it defaults to
postgresql://localhost/datum. `serve` binds a single dev principal for the
whole stdio session — a real multi-tenant deployment binds a principal
per connection from an auth backend (mcp_server.auth_middleware), which is
why that binding is a documented dev-only convenience here, not the
production identity path.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click

from datum import __version__
from datum.kernel.principal import Principal

_DEFAULT_DSN = os.environ.get("DATUM_PG_DSN", "postgresql://localhost/datum")


@click.group()
@click.version_option(version=__version__, prog_name="datum")
def main() -> None:
    """Datum: a retrieval substrate for the agentic era."""


# Extensions the dependency-free MarkdownParser reads directly as text; every
# other format is routed to Docling (docx, pptx, xlsx, pdf, html, csv, …).
_PLAINTEXT_SUFFIXES = {".md", ".markdown", ".txt", ""}


@main.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--source-id", default=None, help="Source id for the document (defaults to the filename).")
@click.option("--namespace", required=True, help="ACL namespace to ingest into (the writer's partition).")
@click.option("--dsn", default=_DEFAULT_DSN, help="Postgres DSN.")
def ingest(path: Path, source_id: str | None, namespace: str, dsn: str) -> None:
    """Ingest a document from PATH into the corpus.

    Plain text/markdown is read directly; any other format (docx, pptx, xlsx,
    pdf, html, csv, …) is routed through Docling. PDF and image inputs need
    Docling's layout/OCR models, which download from HuggingFace on first use.
    """
    from datum import Corpus

    principal = Principal(id="cli", namespace=namespace)
    sid = source_id or path.name
    is_plaintext = path.suffix.lower() in _PLAINTEXT_SUFFIXES
    with Corpus.open(dsn) as corpus:
        if is_plaintext:
            n = corpus.ingest(sid, path.read_text(encoding="utf-8"), principal=principal)
        else:
            n = corpus.ingest_file(str(path), principal, source_id=sid)
    route = "text" if is_plaintext else "docling"
    click.echo(f"ingested {sid!r} via {route}: {n} write op(s) applied.")


@main.command()
@click.argument("query")
@click.option("--namespace", required=True, help="ACL namespace to search (the caller's partition).")
@click.option("--dsn", default=_DEFAULT_DSN, help="Postgres DSN.")
def search(query: str, namespace: str, dsn: str) -> None:
    """Search the corpus and print the ranked hits."""
    from datum import Corpus

    principal = Principal(id="cli", namespace=namespace)
    with Corpus.open(dsn) as corpus:
        evidence = corpus.search(query, principal=principal)
    click.echo(f"status={evidence.status}  sufficiency={evidence.sufficiency:.3f}  plan={evidence.plan_id}")
    if not evidence.hits:
        click.echo("(no hits)")
        return
    for i, hit in enumerate(evidence.hits, 1):
        section = " > ".join(hit.section_path) if hit.section_path else hit.source_path
        snippet = hit.content.strip().replace("\n", " ")
        if len(snippet) > 200:
            snippet = snippet[:197] + "..."
        click.echo(f"\n[{i}] {section}\n    {snippet}")


@main.command()
@click.option("--namespace", required=True, help="Dev principal's namespace bound for the stdio session.")
@click.option("--dsn", default=_DEFAULT_DSN, help="Postgres DSN.")
def serve(namespace: str, dsn: str) -> None:
    """Run the MCP server over stdio (point an MCP client at this)."""
    from datum import Corpus
    from datum.mcp_server.server import build_server
    from datum.security.context import bind_principal

    principal = Principal(id="cli-dev", namespace=namespace)
    corpus = Corpus.open(dsn)
    server = build_server(corpus)
    click.echo(
        f"datum MCP server: 6 verbs, namespace={namespace!r}, dsn={dsn!r}. "
        "Serving over stdio (dev principal bound for the whole session).",
        err=True,
    )
    try:
        # Dev-only: one principal for the whole stdio session. The contextvar
        # is copied into the server's worker-thread dispatch, so every tool
        # call sees it. Production binds per-connection in auth_middleware.
        with bind_principal(principal):
            server.run()
    finally:
        corpus.close()


@main.command()
@click.option(
    "--corpus-dir",
    default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Fixture corpus directory (defaults to the bundled sample corpus).",
)
@click.option(
    "--regression-set",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Regression set file (defaults to the bundled fixture set).",
)
@click.option("--dsn", default=_DEFAULT_DSN, help="Postgres DSN (use a SCRATCH db — eval ingests fixture content).")
def eval(corpus_dir: Path | None, regression_set: Path | None, dsn: str) -> None:
    """Run the fixed regression set as a gate against real retrieval.

    Ingests the fixture corpus into DSN and runs every curated case through
    the live hybrid pipeline, exiting non-zero if any case regresses. Point
    --dsn at a scratch database: this INGESTS fixture content (the same
    TEST-SAFETY discipline the suite follows).
    """
    from datum import Corpus
    from datum.eval.gate import (
        DEFAULT_CORPUS_DIR,
        DEFAULT_REGRESSION_SET,
        GATE_ABSTAIN_FLOOR,
        run_gate,
    )

    corpus = Corpus.open(dsn, abstain_min_similarity=GATE_ABSTAIN_FLOOR)
    try:
        report = run_gate(
            corpus,
            corpus_dir=corpus_dir or DEFAULT_CORPUS_DIR,
            regression_set=regression_set or DEFAULT_REGRESSION_SET,
        )
    finally:
        corpus.close()

    passed = sum(1 for _, ok, _ in report.results if ok)
    for case, ok, detail in report.results:
        mark = "PASS" if ok else "FAIL"
        click.echo(f"[{mark}] ({case.principal_namespace}) {case.query}")
        if not ok:
            click.echo(f"       {detail}")
    click.echo(f"\neval gate: {passed}/{len(report.results)} cases passed.")
    if not report.passed:
        raise SystemExit(1)


@main.command()
@click.option("--dsn", default=_DEFAULT_DSN, help="Postgres DSN (use a SCRATCH db — benchmark ingests generated files).")
def benchmark(dsn: str) -> None:
    """Run the multi-format ingestion benchmark (task #30).

    Generates one file per working format family (md/txt/html/csv/docx/pptx/
    xlsx), ingests each through its parser, and checks its fact is retrievable
    via the hybrid pipeline. Reports per-format results and the format families
    skipped in this environment (with reasons). Point --dsn at a scratch db.
    """
    import tempfile

    from datum import Corpus
    from datum.eval.multiformat_benchmark import run_benchmark

    with Corpus.open(dsn) as corpus, tempfile.TemporaryDirectory() as tmp:
        report = run_benchmark(corpus, Path(tmp))

    passed = sum(1 for r in report.results if r.ingested and r.retrieved)
    for r in report.results:
        mark = "PASS" if (r.ingested and r.retrieved) else "FAIL"
        click.echo(f"[{mark}] {r.fmt:6} {r.detail}")
    for fmt, reason in report.skipped:
        click.echo(f"[SKIP] {fmt:14} {reason}")
    click.echo(f"\nmulti-format benchmark: {passed}/{len(report.results)} covered formats passed.")
    if not report.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    sys.exit(main())


@main.command()
@click.option("--namespace", required=True, help="Namespace whose feedback to calibrate on.")
@click.option("--dsn", default=_DEFAULT_DSN, help="Postgres DSN.")
def calibrate(namespace: str, dsn: str) -> None:
    """Tune this namespace's retrieval policy from accumulated relevance
    feedback (the `feedback` MCP verb / Corpus.feedback). Promotion-gated:
    the tuned parameters take effect ONLY if they beat the current policy on
    held-out judgments; otherwise nothing changes and the reason is printed.
    """
    from datum.corpus import Corpus
    from datum.eval.calibrate import run_calibration

    with Corpus.open(dsn) as corpus:
        result = run_calibration(corpus, namespace)
    click.echo(f"judged queries: {result.n_queries}")
    if result.params:
        click.echo(f"best params (train MRR {result.train_mrr:.4f}): {result.params}")
        click.echo(
            f"holdout MRR {result.holdout_mrr:.4f} vs current {result.baseline_holdout_mrr:.4f}"
        )
    click.echo(("PROMOTED — " if result.promoted else "NOT promoted — ") + result.reason)


@main.command("serve-http")
@click.option("--namespace", required=True, help="ACL namespace this server instance serves.")
@click.option("--dsn", default=_DEFAULT_DSN, help="Postgres DSN.")
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind address.")
@click.option("--port", default=8787, show_default=True, type=int, help="Bind port.")
@click.option(
    "--token",
    envvar="DATUM_HTTP_TOKEN",
    default=None,
    help="Bearer token clients must present (or set DATUM_HTTP_TOKEN). Required.",
)
def serve_http(namespace: str, dsn: str, host: str, port: int, token: str | None) -> None:
    """Run the plain HTTP JSON API (the non-MCP way in): the same six verbs,
    callable from any language. One namespace per server process, bearer-token
    required, binds localhost by default."""
    from datum import Corpus
    from datum.http_api import build_http_server

    if not token:
        raise click.UsageError(
            "a bearer token is required: pass --token or set DATUM_HTTP_TOKEN. "
            "There is no anonymous mode."
        )
    corpus = Corpus.open(dsn)
    server = build_http_server(corpus, namespace=namespace, token=token, host=host, port=port)
    click.echo(
        f"datum HTTP API: 6 verbs at http://{host}:{port}/v1/*, namespace={namespace!r}, "
        f"dsn={dsn!r}. POST JSON with 'Authorization: Bearer <token>'.",
        err=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
