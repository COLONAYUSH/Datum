/**
 * Tests the CLIENT's transport behavior (request shape, headers, error
 * mapping) against a small real HTTP server standing in for
 * `datum serve-http` — not retrieval quality, which is covered where the
 * real server lives (the main repository's `tests/mcp_server/test_http_api.py`).
 * No mocking of fetch itself: this is a real HTTP round trip over a real
 * socket on an ephemeral port, exactly like a consumer's own code would do.
 */
import assert from "node:assert/strict";
import http from "node:http";
import { after, before, describe, test } from "node:test";

import { DatumClient, DatumError } from "../src/index.ts";

const TOKEN = "test-token";
let server: http.Server;
let baseUrl: string;
let lastRequest: { method?: string; path?: string; headers?: http.IncomingHttpHeaders; body?: unknown } = {};

before(async () => {
  server = http.createServer((req, res) => {
    let raw = "";
    req.on("data", (chunk) => (raw += chunk));
    req.on("end", () => {
      lastRequest = {
        method: req.method,
        path: req.url,
        headers: req.headers,
        body: raw ? JSON.parse(raw) : undefined,
      };
      const send = (status: number, payload: unknown) => {
        res.writeHead(status, { "Content-Type": "application/json" });
        res.end(JSON.stringify(payload));
      };

      const auth = req.headers.authorization;
      if (req.url === "/v1/health") {
        send(200, { ok: true });
        return;
      }
      if (auth !== `Bearer ${TOKEN}`) {
        send(401, { error: "missing or invalid bearer token" });
        return;
      }
      if (req.url === "/v1/search") {
        send(200, {
          result: {
            hits: [
              {
                hit_id: "abc.def",
                content: "roll back by promoting the previous release tag",
                source_path: "runbook.md",
                section_path: ["runbook.md", "Rollback"],
                page: null,
                score: null,
              },
            ],
            status: "ok",
            sufficiency: 0.71,
            plan_id: "pl_123",
          },
        });
      } else if (req.url === "/v1/fetch") {
        send(200, {
          result: {
            hit_id: "abc.def",
            content: "roll back by promoting the previous release tag",
            source_path: "runbook.md",
            section_path: ["runbook.md", "Rollback"],
            page: null,
            score: null,
          },
        });
      } else if (req.url === "/v1/navigate") {
        send(200, { result: { root: { path: "runbook.md", kind: "document", children: [], hit_id: null } } });
      } else if (req.url === "/v1/explain") {
        send(200, { result: "acl_filter -> search(operator='bm25') -> sufficiency_check" });
      } else if (req.url === "/v1/since") {
        send(200, { result: { changes: [], since_marker: "", as_of_marker: "wal-9" } });
      } else if (req.url === "/v1/feedback") {
        send(200, { result: { recorded: true } });
      } else if (req.url === "/v1/forged") {
        send(400, { error: "unknown or forged hit_id" });
      } else {
        send(404, { error: "not found" });
      }
    });
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (address === null || typeof address === "string") throw new Error("expected a bound TCP address");
  baseUrl = `http://127.0.0.1:${address.port}`;
});

after(async () => {
  await new Promise<void>((resolve) => server.close(() => resolve()));
});

describe("DatumClient construction", () => {
  test("rejects a missing token", () => {
    assert.throws(() => new DatumClient({ baseUrl: "http://x", token: "" }), /bearer token/);
  });

  test("rejects a whitespace-only token", () => {
    assert.throws(() => new DatumClient({ baseUrl: "http://x", token: "   " }), /bearer token/);
  });

  test("rejects a missing baseUrl", () => {
    assert.throws(() => new DatumClient({ baseUrl: "", token: TOKEN }), /baseUrl/);
  });

  test("strips a trailing slash from baseUrl", async () => {
    const client = new DatumClient({ baseUrl: `${baseUrl}/`, token: TOKEN });
    await client.search("anything");
    assert.equal(lastRequest.path, "/v1/search");
  });
});

describe("search", () => {
  test("sends the bearer token and the query, and parses typed evidence", async () => {
    const client = new DatumClient({ baseUrl, token: TOKEN });
    const evidence = await client.search("how do I roll back a deploy");
    assert.equal(lastRequest.method, "POST");
    assert.equal(lastRequest.headers?.authorization, `Bearer ${TOKEN}`);
    assert.deepEqual(lastRequest.body, { query: "how do I roll back a deploy", path_glob: null });
    assert.equal(evidence.status, "ok");
    assert.equal(evidence.hits.length, 1);
    assert.equal(evidence.hits[0].hit_id, "abc.def");
    assert.ok(evidence.hits[0].content.includes("roll back"));
  });

  test("passes pathGlob through as path_glob", async () => {
    const client = new DatumClient({ baseUrl, token: TOKEN });
    await client.search("deploy", { pathGlob: "runbooks/**" });
    assert.deepEqual(lastRequest.body, { query: "deploy", path_glob: "runbooks/**" });
  });
});

describe("the other five verbs round-trip", () => {
  // Constructed inside each test, not at describe-registration time: describe
  // callbacks run synchronously as soon as they're registered, before the
  // top-level before() hook below has set `baseUrl` — a real bug this test
  // file had until it was run once and failed.
  test("fetchHit", async () => {
    const client = new DatumClient({ baseUrl, token: TOKEN });
    const hit = await client.fetchHit("abc.def");
    assert.deepEqual(lastRequest.body, { hit_id: "abc.def" });
    assert.equal(hit.source_path, "runbook.md");
  });

  test("navigate", async () => {
    const client = new DatumClient({ baseUrl, token: TOKEN });
    const view = await client.navigate("runbook.md");
    assert.deepEqual(lastRequest.body, { ref: "runbook.md", depth: null });
    assert.equal(view.root.path, "runbook.md");
  });

  test("explain", async () => {
    const client = new DatumClient({ baseUrl, token: TOKEN });
    const explanation = await client.explain("pl_123");
    assert.deepEqual(lastRequest.body, { plan_id: "pl_123" });
    assert.equal(typeof explanation, "string");
    assert.ok(explanation.includes("acl_filter"));
  });

  test("since defaults the marker to empty string", async () => {
    const client = new DatumClient({ baseUrl, token: TOKEN });
    const changes = await client.since();
    assert.deepEqual(lastRequest.body, { marker: "" });
    assert.equal(changes.as_of_marker, "wal-9");
  });

  test("feedback", async () => {
    const client = new DatumClient({ baseUrl, token: TOKEN });
    const result = await client.feedback("abc.def", true);
    assert.deepEqual(lastRequest.body, { hit_id: "abc.def", useful: true });
    assert.equal(result.recorded, true);
  });

  test("health needs no token and returns a boolean", async () => {
    const unauthenticatedClient = new DatumClient({ baseUrl, token: "irrelevant-for-health" });
    assert.equal(await unauthenticatedClient.health(), true);
  });
});

describe("error mapping", () => {
  test("a wrong token surfaces as a DatumError with status 401", async () => {
    const client = new DatumClient({ baseUrl, token: "wrong-token" });
    await assert.rejects(
      () => client.search("anything"),
      (err: unknown) => {
        assert.ok(err instanceof DatumError);
        assert.equal(err.status, 401);
        assert.match(err.message, /token/);
        return true;
      }
    );
  });

  test("a forged hit id surfaces as a 400, never a thrown non-Datum error", async () => {
    const client = new DatumClient({ baseUrl, token: TOKEN });
    await assert.rejects(
      () => (client as unknown as { post: (p: string, b: object) => Promise<unknown> }).post("/v1/forged", {}),
      (err: unknown) => {
        assert.ok(err instanceof DatumError);
        assert.equal(err.status, 400);
        return true;
      }
    );
  });

  test("an unknown route is a 404 DatumError", async () => {
    const client = new DatumClient({ baseUrl, token: TOKEN });
    await assert.rejects(
      () => (client as unknown as { post: (p: string, b: object) => Promise<unknown> }).post("/v1/nonexistent", {}),
      (err: unknown) => {
        assert.ok(err instanceof DatumError);
        assert.equal(err.status, 404);
        return true;
      }
    );
  });
});
