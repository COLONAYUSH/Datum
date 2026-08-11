"""Milestone D acceptance: the Agent Tool Surface driven END TO END through a
REAL MCP client over the REAL stdio transport against a REAL running server.

This is the plan's final checkpoint, minus the one part that cannot run
headlessly: a live LLM autonomously *choosing* to call the verbs. Everything
below that is exercised for real — a `datum serve` subprocess (its own
process, its own Corpus, the actual bge embedder + cross-encoder), the stdio
JSON-RPC framing, the MCP `initialize` handshake, `list_tools`, and each of
the five read verbs called as a client calls them, with the results decoded
off the wire. The tool calls made here are exactly the ones a tool-calling
model would emit; only the model's decision to emit them is stubbed.

Skips without a reachable Postgres or the `datum[embed]` extra (the server
loads real models). Set `HF_HUB_OFFLINE=1` in the environment or the server
subprocess can hang on HuggingFace's network HEAD checks — the harness passes
it through below.
"""

from __future__ import annotations

import json

import importlib.util
import os
import sys

import psycopg
import pytest

from datum.corpus import Corpus
from datum.kernel.principal import Principal

_DSN = os.environ.get("DATUM_PG_DSN", "postgresql://localhost/datum")


def _pg_reachable(dsn: str) -> bool:
    try:
        with psycopg.connect(dsn, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


pytestmark = [
    pytest.mark.skipif(
        not _pg_reachable(_DSN), reason=f"no reachable Postgres at DATUM_PG_DSN={_DSN!r}"
    ),
    pytest.mark.skipif(
        importlib.util.find_spec("sentence_transformers") is None,
        reason="the datum[embed] extra is not installed; the MCP server loads real models",
    ),
]

_RUNBOOK = (
    "# Deploy Runbook\n\n"
    "## Rollback\n\n"
    "If a deploy goes wrong, roll back by pinning the previous image tag and redeploying.\n\n"
    "## Incident response\n\n"
    "Page the on-call engineer if the error rate exceeds five percent for ten minutes.\n"
)


@pytest.fixture
def ingested_dsn():
    """A scratch DB with one known document ingested and the views derived,
    ready for a `datum serve` subprocess to read.
    """
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS view_dense")  # embedder dim may change (bge-m3: 1024)
    c = Corpus.open(_DSN, hit_signing_key=b"e2e-key")
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE TABLE records RESTART IDENTITY CASCADE")
        conn.execute("TRUNCATE TABLE wal_entries RESTART IDENTITY")
        conn.execute("TRUNCATE TABLE plan_traces")
        conn.execute("TRUNCATE TABLE view_cursors")
        conn.execute("DELETE FROM view_lexical")
    c.ingest("runbook.md", _RUNBOOK, principal=Principal(id="ingestor", namespace="tenant:acme"))
    # Give the outsider tenant its OWN matching content, so the fail-closed
    # test below cannot pass merely because that namespace is empty (an empty
    # namespace abstains regardless of tenancy — the false-green to avoid).
    c.ingest(
        "outsider_runbook.md",
        "# Ops\n\n## Reverting\n\nTo undo a broken release, roll back to the last known good build.\n",
        principal=Principal(id="ingestor", namespace="tenant:outsider"),
    )
    c.close()
    return _DSN


def _server_params(namespace: str, dsn: str):
    from mcp.client.stdio import StdioServerParameters

    env = {
        **os.environ,
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "DATUM_HIT_SIGNING_KEY": "e2e-key",
        "DATUM_PG_DSN": dsn,
    }
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "datum.cli", "serve", "--namespace", namespace, "--dsn", dsn],
        env=env,
    )


def _payload(result):
    """Decode a CallToolResult into a plain dict/text: structured_content when
    the tool returned a typed value, else the first text content block.
    """
    if result.structured_content is not None:
        return result.structured_content
    return result.content[0].text if result.content else None


async def _drive(namespace: str, dsn: str) -> dict:
    """Run one client session against a fresh server subprocess bound to
    `namespace`, exercising all six verbs. Returns the decoded results.
    """
    import asyncio

    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client

    out: dict = {}
    async with stdio_client(_server_params(namespace, dsn)) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=120)

            tools = await session.list_tools()
            out["tools"] = sorted(t.name for t in tools.tools)

            search = _payload(await asyncio.wait_for(
                session.call_tool("search", {"query": "how do I roll back a bad deploy"}), timeout=120))
            out["search"] = search

            if search.get("hits"):
                hit_id = search["hits"][0]["hit_id"]
                out["fetch"] = _payload(await session.call_tool("fetch", {"hit_id": hit_id}))
                out["explain"] = _payload(await session.call_tool("explain", {"plan_id": search["plan_id"]}))
                out["feedback"] = _payload(await session.call_tool(
                    "feedback", {"hit_id": hit_id, "useful": True}))

            out["navigate"] = _payload(await session.call_tool("navigate", {"ref": "runbook.md"}))
            out["since"] = _payload(await session.call_tool("since", {"marker": ""}))
    return out


async def test_all_six_verbs_end_to_end_over_real_mcp(ingested_dsn):
    results = await _drive("tenant:acme", ingested_dsn)

    # list_tools exposes exactly the five read verbs.
    assert results["tools"] == ["explain", "feedback", "fetch", "navigate", "search", "since"]

    # search: real hybrid retrieval, the rollback content on top, opaque hit_id.
    search = results["search"]
    assert search["status"] == "ok"
    assert search["hits"], "search returned no hits over MCP"
    top = search["hits"][0]
    assert "roll back" in top["content"].lower()
    assert top["source_path"] == "runbook.md"
    assert top["hit_id"] and "." in top["hit_id"]  # signed token, not raw content
    assert search["plan_id"].startswith("pl_")

    # feedback: the judgment round-trips over the wire and is recorded
    # (fail-closed server-side like fetch — this token IS in-namespace).
    fb = results["feedback"]
    fb = json.loads(fb) if isinstance(fb, str) else fb
    assert fb == {"recorded": True}

    # fetch: the opaque hit_id resolves back to full content over the wire.
    assert "roll back" in results["fetch"]["content"].lower()

    # navigate: structure without materialized text; the Rollback section shows.
    nav = results["navigate"]
    assert nav["root"]["path"] == "runbook.md"
    child_paths = " ".join(str(c.get("path", "")) for c in nav["root"].get("children", []))
    assert "Rollback" in child_paths

    # explain: the EXPLAIN of the search plan names the ACL filter + a search step.
    explain_text = results["explain"] if isinstance(results["explain"], str) else str(results["explain"])
    assert "acl_filter" in explain_text and "search" in explain_text

    # since: the changefeed shows the ingest writes.
    since = results["since"]
    assert since["changes"], "since returned no changes"
    assert since["as_of_marker"]


async def test_namespace_fail_closed_over_real_mcp(ingested_dsn):
    # A server bound to a DIFFERENT tenant sees ONLY its own namespace's
    # content, never acme's — tenancy holds through the real transport,
    # resolved from the session principal, never from a tool argument. The
    # outsider namespace is deliberately NON-EMPTY (fixture) so this passes
    # because isolation holds, not because there was nothing to return.
    results = await _drive("tenant:outsider", ingested_dsn)
    search = results["search"]
    assert search["status"] == "ok"
    assert search["hits"], "outsider should see its OWN content"
    combined = " ".join(h["content"] for h in search["hits"])
    assert "last known good build" in combined  # the outsider's own doc
    assert "pinning the previous image tag" not in combined  # acme's doc did NOT leak
