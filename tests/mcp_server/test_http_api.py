"""The plain HTTP surface (http_api.py), end to end against a real corpus:
a live threading server on an ephemeral port, called with urllib like any
non-Python client would call it. Covers the auth gate (fail-closed, both
missing and wrong token), the six verbs round-tripping JSON, forged-hit
handling as a 400 (never a stack trace), and the health probe."""

from __future__ import annotations

import importlib.util
import json
import os
import threading
import urllib.error
import urllib.request

import psycopg
import pytest

from datum.corpus import Corpus
from datum.http_api import build_http_server
from datum.kernel.errors import DatumError
from datum.kernel.principal import Principal

_DSN = os.environ.get("DATUM_PG_DSN", "postgresql://localhost/datum")
_NS = "tenant:http"
_TOKEN = "test-token-http"


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
        reason="the datum[embed] extra is not installed",
    ),
]


@pytest.fixture(scope="module")
def served():
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS view_dense")
    corpus = Corpus.open(_DSN, hit_signing_key=b"http-key", abstain_min_similarity=0.0)
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE TABLE records RESTART IDENTITY CASCADE")
        conn.execute("TRUNCATE TABLE wal_entries RESTART IDENTITY")
        conn.execute("TRUNCATE TABLE plan_traces")
        conn.execute("TRUNCATE TABLE view_cursors")
        conn.execute("TRUNCATE TABLE relevance_feedback")
        conn.execute("DELETE FROM view_lexical")
    corpus.ingest(
        "runbook.md",
        "# Rollback\nTo roll back a bad deploy, promote the previous release tag.",
        Principal(id="writer", namespace=_NS),
    )
    server = build_http_server(corpus, namespace=_NS, token=_TOKEN, port=0)  # ephemeral port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    yield base
    server.shutdown()
    corpus.close()


def _post(base: str, path: str, payload: dict, token: str | None = _TOKEN) -> tuple[int, dict]:
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
        | ({"Authorization": f"Bearer {token}"} if token else {}),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as err:
        return err.code, json.load(err)


def test_health_is_open_and_reveals_nothing(served):
    with urllib.request.urlopen(served + "/v1/health", timeout=10) as resp:
        assert resp.status == 200
        assert json.load(resp) == {"ok": True}


def test_auth_fails_closed_without_and_with_wrong_token(served):
    code, body = _post(served, "/v1/search", {"query": "roll back"}, token=None)
    assert code == 401 and "token" in body["error"]
    code, body = _post(served, "/v1/search", {"query": "roll back"}, token="wrong-token")
    assert code == 401


def test_search_fetch_explain_feedback_round_trip(served):
    code, body = _post(served, "/v1/search", {"query": "how do I roll back a bad deploy"})
    assert code == 200
    result = body["result"]
    assert result["status"] == "ok" and result["hits"]
    top = result["hits"][0]
    assert "roll back" in top["content"].lower()
    assert top["hit_id"] and result["plan_id"].startswith("pl_")

    code, body = _post(served, "/v1/fetch", {"hit_id": top["hit_id"]})
    assert code == 200 and "previous release tag" in body["result"]["content"]

    code, body = _post(served, "/v1/explain", {"plan_id": result["plan_id"]})
    assert code == 200 and "acl_filter" in body["result"]

    code, body = _post(served, "/v1/feedback", {"hit_id": top["hit_id"], "useful": True})
    assert code == 200 and body["result"] == {"recorded": True}


def test_navigate_and_since_serialize(served):
    code, body = _post(served, "/v1/navigate", {"ref": "runbook.md"})
    assert code == 200 and body["result"]["root"]["path"] == "runbook.md"
    code, body = _post(served, "/v1/since", {"marker": ""})
    assert code == 200 and "as_of_marker" in body["result"]


def test_forged_hit_is_a_400_not_a_traceback(served):
    code, body = _post(served, "/v1/fetch", {"hit_id": "forged.payload.signature"})
    assert code == 400
    assert "error" in body and "Traceback" not in body["error"]


def test_unknown_route_and_missing_field_are_client_errors(served):
    code, _ = _post(served, "/v1/nonsense", {"x": 1})
    assert code == 404
    code, body = _post(served, "/v1/search", {})  # missing "query"
    assert code == 400


def test_server_refuses_to_build_without_a_token():
    with pytest.raises(DatumError, match="bearer token"):
        build_http_server(object(), namespace=_NS, token="  ")
