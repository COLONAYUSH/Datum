/**
 * A thin client for Datum's HTTP surface (`datum serve-http`).
 *
 * This is NOT a JavaScript port of the framework. Datum's core — the
 * write-ahead log, the bitemporal store, the conformance-gated operators,
 * the compiled plan — is Python and PostgreSQL by design (see the main
 * repository's README and docs/decisions.md). This package is a wire client:
 * it POSTs JSON to a running `datum serve-http` process and parses the
 * response into typed values, nothing more. Retrieval behavior, tenancy, and
 * every guarantee described in the main project live entirely on the
 * server; this client trusts none of it and enforces none of it.
 *
 * Field names on the wire match the server's Python dataclasses exactly
 * (snake_case: `hit_id`, `section_path`, `since_marker`, ...) because the
 * server serializes them verbatim. Method options on this client are
 * camelCase, the normal JS convention; the client translates at the edge.
 */

export interface SearchHit {
  hit_id: string;
  content: string;
  source_path: string;
  section_path: string[];
  page: number | null;
  score: number | null;
}

export type EvidenceStatus = "ok" | "insufficient_evidence" | "error";

export interface Evidence {
  hits: SearchHit[];
  status: EvidenceStatus;
  sufficiency: number;
  plan_id: string;
}

export type StructureNodeKind = "document" | "section" | "table" | "page";

export interface StructureNode {
  path: string;
  kind: StructureNodeKind;
  children: StructureNode[];
  hit_id: string | null;
}

export interface StructureView {
  root: StructureNode;
}

export type ChangeKind = "created" | "superseded" | "forgotten";

export interface ChangeRecord {
  hit_id: string;
  change_kind: ChangeKind;
  occurred_at: string; // ISO 8601; the server serializes datetimes this way
}

export interface ChangeSet {
  changes: ChangeRecord[];
  since_marker: string;
  as_of_marker: string;
}

export interface FeedbackResult {
  recorded: boolean;
}

/**
 * Raised for every non-2xx response. `status` is the HTTP status code the
 * server sent — 400 for a bad request or a resolved-but-invalid hit id
 * (never a stack trace), 401 for a missing or wrong bearer token, 404 for
 * an unknown route, 500 for an unexpected server-side failure. `message`
 * is the server's own error text when it sent one.
 */
export class DatumError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "DatumError";
    this.status = status;
  }
}

export interface DatumClientOptions {
  /** e.g. "http://127.0.0.1:8787" — no trailing slash required. */
  baseUrl: string;
  /** The bearer token `datum serve-http` was started with. Required; the
   * server has no anonymous mode, and neither does this client. */
  token: string;
  /** Override for testing or to point at a fetch polyfill; defaults to the
   * runtime's global `fetch`. */
  fetch?: typeof globalThis.fetch;
}

/** A client for one Datum server, bound to one namespace (the server binds
 * its namespace at startup, not per-request — see the HTTP API's design
 * notes in the main repository). Construct one per server you talk to. */
export class DatumClient {
  private readonly baseUrl: string;
  private readonly token: string;
  private readonly fetchImpl: typeof globalThis.fetch;

  constructor(options: DatumClientOptions) {
    if (!options.token || !options.token.trim()) {
      throw new Error(
        "DatumClient requires a bearer token (the one 'datum serve-http' was started with). " +
          "There is no anonymous mode."
      );
    }
    if (!options.baseUrl || !options.baseUrl.trim()) {
      throw new Error("DatumClient requires baseUrl, e.g. 'http://127.0.0.1:8787'.");
    }
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.token = options.token;
    this.fetchImpl = options.fetch ?? globalThis.fetch;
  }

  private async post<T>(path: string, body: Record<string, unknown>): Promise<T> {
    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.token}`,
      },
      body: JSON.stringify(body),
    });
    let payload: { result?: T; error?: string };
    try {
      payload = (await response.json()) as { result?: T; error?: string };
    } catch {
      throw new DatumError(
        `${path} returned a non-JSON response (status ${response.status})`,
        response.status
      );
    }
    if (!response.ok) {
      throw new DatumError(payload.error ?? `${path} failed with status ${response.status}`, response.status);
    }
    return payload.result as T;
  }

  /** Search the corpus. `pathGlob` narrows to a subset of sources, e.g.
   * "contracts/**". Returns typed evidence, including a `status` that can
   * be "insufficient_evidence" — check it before trusting `hits`. */
  search(query: string, options: { pathGlob?: string } = {}): Promise<Evidence> {
    return this.post<Evidence>("/v1/search", { query, path_glob: options.pathGlob ?? null });
  }

  /** Resolve a `hit_id` from an earlier `search`/`navigate` call to its full
   * content. Named `fetchHit`, not `fetch`, to avoid colliding with the
   * platform's global `fetch` this client itself is built on. */
  fetchHit(hitId: string): Promise<SearchHit> {
    return this.post<SearchHit>("/v1/fetch", { hit_id: hitId });
  }

  /** Structure only, no text materialized — explore before you fetch. */
  navigate(ref: string, options: { depth?: number } = {}): Promise<StructureView> {
    return this.post<StructureView>("/v1/navigate", { ref, depth: options.depth ?? null });
  }

  /** The human-readable EXPLAIN of a previously executed plan. */
  explain(planId: string): Promise<string> {
    return this.post<string>("/v1/explain", { plan_id: planId });
  }

  /** The change feed since an opaque marker (pass "" to start from the
   * beginning of the retained log). */
  since(marker: string = ""): Promise<ChangeSet> {
    return this.post<ChangeSet>("/v1/since", { marker });
  }

  /** Record whether a previously returned hit was actually useful. Feeds
   * the server's calibration loop (`datum calibrate`); has no effect on
   * the current search's results. */
  feedback(hitId: string, useful: boolean): Promise<FeedbackResult> {
    return this.post<FeedbackResult>("/v1/feedback", { hit_id: hitId, useful });
  }

  /** The one unauthenticated endpoint: true if the server is up. Reveals
   * nothing else, by design. */
  async health(): Promise<boolean> {
    const response = await this.fetchImpl(`${this.baseUrl}/v1/health`);
    return response.ok;
  }
}
