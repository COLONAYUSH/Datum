"""A plain HTTP surface over the six verbs (L8, sibling of the MCP server).

MCP is the agent-native way in; this is the everyone-else way in. Any language
that can POST JSON — Node, Go, a shell script — gets the same six verbs the
MCP server exposes, backed by the same Corpus, with the same fail-closed
tenancy semantics. Nothing here adds retrieval behavior: every endpoint is a
thin, auditable translation from JSON to the corpus call the Python API makes.

Deliberate choices, stated so they are not mistaken for oversights:

- **Standard library only.** No web framework: `http.server`'s threading
  server is enough for a six-endpoint JSON API, keeps the core dependency
  list unchanged, and means `pip install datum` is all a deployment needs.
- **A bearer token is REQUIRED.** There is no anonymous mode to misconfigure.
  The server refuses to construct without a token, and comparison is
  constant-time. This is transport auth, not the tenancy model — the
  namespace partition is still resolved per-request inside the corpus and
  still fails closed; the token only decides whether a request is spoken to
  at all.
- **One namespace per server process,** exactly like `datum serve` for MCP:
  the principal is bound at startup, not taken from the request body, so a
  compromised client cannot ask for someone else's partition by editing JSON.
  Multi-tenant deployments run one process per tenant or put a real gateway
  in front; pretending this server is that gateway would be the kind of
  quiet overreach the rest of the design exists to prevent.
- **Errors are structured and unrevealing.** Bad input is a 400 with a short
  message; a forged or stale hit id is a 400, not a stack trace; anything
  unexpected is a 500 with no internals leaked. The full detail still lands
  in the server process log, and failed searches still persist their audit
  trace like every other path (decisions.md #27).

Endpoints (all POST, JSON in, JSON out; `GET /v1/health` is the one
unauthenticated liveness probe and reveals nothing but liveness):

    POST /v1/search    {"query": str, "path_glob": str|null}
    POST /v1/fetch     {"hit_id": str}
    POST /v1/navigate  {"ref": str, "depth": int|null}
    POST /v1/explain   {"plan_id": str}
    POST /v1/since     {"marker": str}
    POST /v1/feedback  {"hit_id": str, "useful": bool}
"""

from __future__ import annotations

import dataclasses
import hmac
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from datum.kernel.errors import DatumError
from datum.kernel.principal import Principal

_MAX_BODY_BYTES = 1_000_000  # a verb call is small; anything bigger is abuse


def _jsonable(value: Any) -> Any:
    """Surface types (frozen dataclasses of tuples) to plain JSON values."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {k: _jsonable(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def build_http_server(
    corpus,
    *,
    namespace: str,
    token: str,
    principal_id: str = "http-client",
    host: str = "127.0.0.1",
    port: int = 8787,
) -> ThreadingHTTPServer:
    """A ready-to-serve ThreadingHTTPServer bound to `host:port`. The caller
    owns its lifecycle (`serve_forever()` / `shutdown()`). Refuses an empty
    token — there is no anonymous configuration of this surface."""
    if not token or not token.strip():
        raise DatumError(
            "the HTTP surface requires a bearer token; refusing to serve without one. "
            "Pass token=... (or --token / DATUM_HTTP_TOKEN via the CLI)."
        )
    principal = Principal(id=principal_id, namespace=namespace)
    expected = token.strip()

    class Handler(BaseHTTPRequestHandler):
        server_version = "datum-http"

        # --- plumbing -------------------------------------------------------
        def _send(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            header = self.headers.get("Authorization", "")
            supplied = header[7:] if header.startswith("Bearer ") else ""
            return hmac.compare_digest(supplied.encode(), expected.encode())

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            if length > _MAX_BODY_BYTES:
                raise ValueError(f"request body exceeds {_MAX_BODY_BYTES} bytes")
            raw = self.rfile.read(length) if length else b"{}"
            parsed = json.loads(raw.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("request body must be a JSON object")
            return parsed

        def log_message(self, fmt: str, *args: Any) -> None:  # quiet by default
            pass

        # --- routes ---------------------------------------------------------
        def do_GET(self) -> None:
            if self.path == "/v1/health":
                self._send(200, {"ok": True})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self) -> None:
            if not self._authorized():
                self._send(401, {"error": "missing or invalid bearer token"})
                return
            try:
                body = self._body()
                if self.path == "/v1/search":
                    result = corpus.search(
                        str(body["query"]),
                        principal=principal,
                        path_glob=body.get("path_glob"),
                    )
                elif self.path == "/v1/fetch":
                    result = corpus.fetch(str(body["hit_id"]), principal=principal)
                elif self.path == "/v1/navigate":
                    result = corpus.navigate(
                        str(body["ref"]), principal=principal, depth=body.get("depth")
                    )
                elif self.path == "/v1/explain":
                    result = corpus.explain(str(body["plan_id"]), principal=principal)
                elif self.path == "/v1/since":
                    result = corpus.since(str(body.get("marker", "")), principal=principal)
                elif self.path == "/v1/feedback":
                    result = {
                        "recorded": corpus.feedback(
                            str(body["hit_id"]), bool(body["useful"]), principal=principal
                        )
                    }
                else:
                    self._send(404, {"error": "not found"})
                    return
                self._send(200, {"result": _jsonable(result)})
            except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
                self._send(400, {"error": f"bad request: {exc}"})
            except DatumError as exc:
                # includes forged/stale hit ids — a client error, not a crash,
                # and never a stack trace over the wire
                self._send(400, {"error": str(exc)})
            except Exception:
                self._send(500, {"error": "internal error"})
                raise  # still reaches the server log; never the client

    return ThreadingHTTPServer((host, port), Handler)
