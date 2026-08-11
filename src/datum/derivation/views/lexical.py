"""LexicalView: the L4 BM25-shaped lexical view, backed by Postgres FTS
(tsvector + GIN).

decisions.md #4 made the BM25 backing a go/no-go, not a pin: try ParadeDB
pg_search first, fall back to Postgres tsvector+GIN if install friction is
real. The go/no-go resolved NO-GO (pg_search is not installed here), so this
module is the sanctioned fallback: a BM25-SHAPED lexical view — server-side
lexemes at derive time, ts_rank_cd ranking at query time (operators/bm25_op.py)
— not BM25's exact formula. The conformance suite's score contract is
deliberately "monotonic in relevance," never "matches BM25's formula"
(#4 again), precisely so this backend and a later pg_search swap pass the
same gate behind the same view/operator surface.

Tokenization happens in SQL, in ONE place: derive() computes
`to_tsvector(<config>, body_text)` server-side, so the lexemes stored in the
index come from the same Postgres FTS configuration that
websearch_to_tsquery() applies to query text. A Python-side tokenizer would
be a second implementation free to drift from the query parser's — the exact
canonical-tokenization split this view exists to avoid.

Contract discipline is base.py's: rows are keyed by `records.row_id` (the
surrogate PK — record_id legitimately recurs across versions/spans);
`derive`/`remove` run on the caller's cursor and never commit or roll back
(the engine owns the transaction, same seam as decisions.md #11);
`ensure_schema` takes the connection and owns its DDL, because views own
their schema rather than a numbered migration (0004_views.sql header).

The `namespace` column here is a read-path optimization ONLY. At query time
the bm25 operator joins back to `records` and re-checks namespace
(exact-equality, decisions.md #13) and liveness against L2, the source of
truth — a stale view row can never widen visibility. `producer_version`
embeds the FTS config, so re-deriving under a different config is detectable
as a producer change (the CI-07 lineage tuple), not a silent re-tokenization.
"""

from __future__ import annotations

from typing import Any, Sequence

import psycopg

from datum.derivation.views.base import RecordRow, contextual_text

_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS view_lexical (
    row_id           BIGINT PRIMARY KEY REFERENCES records(row_id) ON DELETE CASCADE,
    record_id        TEXT NOT NULL,
    namespace        TEXT NOT NULL,
    producer_version TEXT NOT NULL,
    tsv              tsvector NOT NULL
)
"""

_TSV_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS view_lexical_tsv_idx
    ON view_lexical USING GIN (tsv)
"""

_NAMESPACE_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS view_lexical_namespace_idx
    ON view_lexical (namespace)
"""

# Postgres caps a tsvector at ~1MB of lexemes; a body_text whose tokenized
# form exceeds that makes to_tsvector RAISE, which (inside the engine's batch
# transaction) rolls back the whole batch AND the WAL-cursor advance, so every
# later refresh re-reads the poison entry and re-raises — one oversized record
# wedges the whole namespace's derivation permanently (review finding H2). The
# real write path can't produce this (the chunker bounds prose to 4096 chars),
# but a raw GroundStore.apply can. The indexed text is therefore capped
# server-side with left(): a disposable index over the first N characters of a
# pathologically-large record is a defensible degradation (the canonical L2
# record is untouched, and N sits far above any real chunk so honest data is
# never truncated), and it turns a permanent wedge into at worst reduced
# recall on one abnormal record.
_MAX_INDEX_CHARS = 200_000


class LexicalView:
    name = "lexical"

    def __init__(self, fts_config: str = "english") -> None:
        self._fts_config = fts_config
        # The config is part of the producer identity: 'english' and 'simple'
        # produce different lexemes for the same text, and a reindex after a
        # config change must be detectable per row (base.py's CI-07 note).
        # v2: context-prefixed input text (contextual BM25 — the same
        # section-path prefix the dense view embeds; see views.dense
        # .contextual_text and decisions.md #41).
        self.producer_version = f"lexical-v2-ctx/pg-tsvector-{fts_config}"

    def ensure_schema(self, conn: psycopg.Connection[Any]) -> None:
        """Create table + indexes if absent. Idempotent (IF NOT EXISTS
        throughout); the table shape is config-independent — the FTS config
        affects row *content*, stamped per row via producer_version, so there
        is no incompatible-existing-table case to refuse here (contrast the
        dense view, whose column type depends on the embedder dimension).
        """
        with conn.transaction():
            conn.execute(_TABLE_DDL)
            conn.execute(_TSV_INDEX_DDL)
            conn.execute(_NAMESPACE_INDEX_DDL)

    def derive(self, cur: psycopg.Cursor[Any], rows: Sequence[RecordRow]) -> int:
        """Project live records into view_lexical on the caller's cursor.
        The tsvector is computed server-side (module docstring: one canonical
        tokenization). Never commits — the engine owns the transaction.
        """
        if not rows:
            return 0
        cur.executemany(
            """
            INSERT INTO view_lexical (row_id, record_id, namespace, producer_version, tsv)
            VALUES (%s, %s, %s, %s, to_tsvector(%s::regconfig, left(%s, %s)))
            """,
            [
                (
                    row.row_id,
                    str(row.record.id),
                    row.record.provenance.writer.namespace,
                    self.producer_version,
                    self._fts_config,
                    contextual_text(row.record),
                    _MAX_INDEX_CHARS,  # left(): cap indexed text so it can't overflow tsvector
                )
                for row in rows
            ],
        )
        return len(rows)

    def remove(self, cur: psycopg.Cursor[Any], row_ids: Sequence[int]) -> int:
        """Delete view rows for `row_ids` on the caller's cursor. Missing
        rows are not an error (idempotent, so a crashed batch can re-run).
        """
        if not row_ids:
            return 0
        cur.execute(
            "DELETE FROM view_lexical WHERE row_id = ANY(%s)",
            (list(row_ids),),
        )
        return cur.rowcount
