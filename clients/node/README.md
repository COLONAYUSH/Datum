# @colonayush/datumrag

A Node/TypeScript client for [Datum](https://github.com/COLONAYUSH/Datum), a retrieval substrate
for AI agents.

**This package is a client, not the framework.** Datum's core — the write-ahead log, the
bitemporal store, the conformance-gated operators, the compiled retrieval plan — is Python and
PostgreSQL, deliberately. This package talks to a running `datum serve-http` server over plain
JSON-over-HTTP and gives you typed methods and types on the JavaScript/TypeScript side; it embeds
none of the retrieval logic itself. If you want the framework, see the
[main repository](https://github.com/COLONAYUSH/Datum) or `pip install datumrag`.

## Install

```bash
npm install @colonayush/datumrag
```

## Run a server to talk to

```bash
pip install 'datumrag[embed]'
DATUM_HTTP_TOKEN=$(openssl rand -hex 24) datum serve-http --namespace tenant:acme --port 8787
```

## Use it

```ts
import { DatumClient } from "@colonayush/datumrag";

const client = new DatumClient({
  baseUrl: "http://127.0.0.1:8787",
  token: process.env.DATUM_HTTP_TOKEN!,
});

const evidence = await client.search("how do I roll back a deploy");
if (evidence.status === "insufficient_evidence") {
  console.log("not enough evidence to answer");
} else {
  for (const hit of evidence.hits) {
    console.log(hit.source_path, "->", hit.content.slice(0, 80));
  }
}
```

CommonJS works too:

```js
const { DatumClient } = require("@colonayush/datumrag");
```

## API

Six methods, one per verb the server exposes — `search`, `fetchHit`, `navigate`, `explain`,
`since`, `feedback` — plus `health()`. Every method returns a typed value (`Evidence`,
`SearchHit`, `StructureView`, `string`, `ChangeSet`, `{ recorded: boolean }`) or throws
`DatumError` with a `status` matching the HTTP status the server sent: 400 for a bad request or an
unresolvable hit id, 401 for a missing or wrong bearer token, 404 for an unknown route, 500 for an
unexpected server-side failure. A forged or stale hit id is always a `DatumError`, never an
unhandled exception with a stack trace.

Field names on the wire are the server's own (`hit_id`, `section_path`, `since_marker`, ...); this
client's method *options* are camelCase (`pathGlob`, not `path_glob`) so the JavaScript-facing
surface reads naturally, and translates at the edge.

```ts
new DatumClient({ baseUrl: string, token: string, fetch?: typeof fetch })

search(query: string, options?: { pathGlob?: string }): Promise<Evidence>
fetchHit(hitId: string): Promise<SearchHit>
navigate(ref: string, options?: { depth?: number }): Promise<StructureView>
explain(planId: string): Promise<string>
since(marker?: string): Promise<ChangeSet>
feedback(hitId: string, useful: boolean): Promise<{ recorded: boolean }>
health(): Promise<boolean>
```

## What this client does and does not enforce

The server, not this client, is the tenancy boundary: `datum serve-http` binds one namespace per
process at startup and requires a bearer token, with no anonymous mode. This client sends whatever
token you give it and trusts the server's responses; it does not re-check permissions, retry, or
cache. If you need a different retry/backoff policy, wrap these calls in your own logic — a thin
client is deliberately not the place for that.

## Development

```bash
npm install
npm test    # runs against a real local HTTP server standing in for datum serve-http
npm run build
```

## License

Apache-2.0, matching the main project.
