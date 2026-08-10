"""DenseView: the L4 dense-embedding view over canonical L2 records.

Implements the ViewBuilder contract (derivation/views/base.py): `derive`/
`remove` run on the ENGINE's cursor and never commit or roll back, so view
rows and the engine's WAL cursor advance together or not at all. The view is
derived and disposable — L2 is the source of truth, and at query time the ANN
operator re-checks namespace and liveness against `records` itself; this
table's own `namespace` column is an optimization, never an authority
(decisions.md #7/#13, FRAMEWORK.md §The architecture, "L4 — Derivation").

Two constraints this module exists to hold:

- **Schema is data-dependent DDL.** The `embedding` column's type is
  `vector(<dim>)` with `<dim>` taken from the configured embedder — DDL that
  cannot be a static numbered migration, which is exactly why views own their
  schema in `ensure_schema` (base.py's module docstring; 0004_views.sql's
  header). `CREATE EXTENSION vector` lives here too, deliberately: core
  migrations must succeed on a Postgres without pgvector, because grep-only
  retrieval never needs it. An existing table whose dimension disagrees with
  the configured embedder is a hard DatumError, never a silent adapt — a
  384-dim index queried with 768-dim vectors is a lineage bug (CI-07), and
  the fix (rebuild the disposable view) is cheap by design.

- **The core system imports without ML extras.** sentence-transformers is the
  optional `datum[embed]` extra (pyproject); `SentenceTransformersEmbedder`
  imports and loads the model on FIRST encode, never at module import or
  construction, so wiring a DenseView (or registering the ANN operator) costs
  nothing in a deployment that never embeds.

Vectors cross the wire as pgvector's text literal with an explicit `::vector`
cast rather than via `pgvector.psycopg.register_vector`: registration
requires the extension's types to already exist on the connection, and this
module must not break connections opened before `ensure_schema` first ran.
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence

import psycopg

from datum.derivation.views.base import RecordRow
from datum.kernel.errors import DatumError


class Embedder(Protocol):
    """What DenseView and the ANN operator require of an embedding model.
    `name`/`version` feed `producer_version` (the CI-07 lineage tuple: a
    model swap must be detectable as a producer change, forcing a rebuild
    of the disposable view rather than a silently mixed index).
    `encode_query` is separate from `encode_documents` because asymmetric
    retrieval models (bge) prepend a query-side instruction.
    """

    name: str  # e.g. "BAAI/bge-small-en-v1.5"
    version: str  # short version tag for lineage, e.g. "st-5.7.0"
    dim: int

    def encode_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def encode_query(self, text: str) -> list[float]: ...


# bge models are trained with this exact instruction on the QUERY side only;
# omitting it measurably degrades retrieval, adding it to documents does too.
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class SentenceTransformersEmbedder:
    """The default local embedder: bge-small-en-v1.5, 384-dim,
    cosine-normalized, CPU-friendly. Lazy on purpose — see module docstring.
    """

    name = "BAAI/bge-small-en-v1.5"
    # Pinned lineage tag for the encoding library, not read from the installed
    # package (that would import it at construction time). Bumping the
    # installed sentence-transformers is expected to bump this tag, which
    # changes producer_version and makes the reindex detectable (CI-07).
    version = "st-5.7.0"
    dim = 384

    def __init__(self) -> None:
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.name, device="cpu")
        return self._model

    def encode_documents(self, texts: Sequence[str]) -> list[list[float]]:
        encoded = self._load().encode(list(texts), normalize_embeddings=True)
        return [[float(x) for x in vec] for vec in encoded]

    def encode_query(self, text: str) -> list[float]:
        encoded = self._load().encode([_BGE_QUERY_PREFIX + text], normalize_embeddings=True)
        return [float(x) for x in encoded[0]]


def vector_literal(vec: Sequence[float]) -> str:
    """A vector as pgvector's text-literal form, for `%s::vector` parameters.
    The one place the wire format is written; ann_op reuses it so the query
    side cannot drift from the derive side.
    """
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


class DenseView:
    name = "dense"

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self.producer_version = f"dense-v1/{embedder.name}@{embedder.version}"

    def ensure_schema(self, conn: psycopg.Connection[Any]) -> None:
        with conn.transaction():
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

        existing_dim = _existing_embedding_dim(conn)
        if existing_dim is not None and existing_dim != self._embedder.dim:
            raise DatumError(
                f"view_dense already exists with embedding dimension {existing_dim}, but the "
                f"configured embedder {self._embedder.name!r}@{self._embedder.version} produces "
                f"dimension {self._embedder.dim}. Refusing to adapt silently: mixing embedders in "
                f"one index corrupts every distance it computes. The view is disposable by design "
                f"— DROP TABLE view_dense and DELETE the 'dense' rows in view_cursors, then let "
                f"the derivation engine rebuild it from L2 with the configured embedder."
            )

        with conn.transaction():
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS view_dense (
                    row_id           BIGINT PRIMARY KEY REFERENCES records(row_id) ON DELETE CASCADE,
                    record_id        TEXT NOT NULL,
                    namespace        TEXT NOT NULL,
                    producer_version TEXT NOT NULL,
                    embedding        vector({int(self._embedder.dim)}) NOT NULL
                )
                """
            )
            # bge embeddings are cosine-normalized, so cosine is the one
            # distance the HNSW index is built for (vector_cosine_ops <=>).
            conn.execute(
                "CREATE INDEX IF NOT EXISTS view_dense_embedding_hnsw_idx "
                "ON view_dense USING hnsw (embedding vector_cosine_ops)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS view_dense_namespace_idx ON view_dense (namespace)"
            )

    def derive(self, cur: psycopg.Cursor[Any], rows: Sequence[RecordRow]) -> int:
        if not rows:
            return 0
        vectors = self._embedder.encode_documents([r.record.body_text() for r in rows])
        cur.executemany(
            "INSERT INTO view_dense (row_id, record_id, namespace, producer_version, embedding) "
            "VALUES (%s, %s, %s, %s, %s::vector)",
            [
                (
                    r.row_id,
                    str(r.record.id),
                    r.record.provenance.writer.namespace,  # decisions.md #7
                    self.producer_version,
                    vector_literal(vec),
                )
                for r, vec in zip(rows, vectors)
            ],
        )
        return len(rows)

    def remove(self, cur: psycopg.Cursor[Any], row_ids: Sequence[int]) -> int:
        if not row_ids:
            return 0
        cur.execute("DELETE FROM view_dense WHERE row_id = ANY(%s)", (list(row_ids),))
        return cur.rowcount


def _existing_embedding_dim(conn: psycopg.Connection[Any]) -> int | None:
    """The dimension of an existing view_dense.embedding column, or None if
    the table does not exist. pgvector stores the declared dimension directly
    as the column's atttypmod (verified against pgvector 0.8.0).
    """
    row = conn.execute(
        "SELECT a.atttypmod FROM pg_attribute a "
        "WHERE a.attrelid = to_regclass('view_dense') AND a.attname = 'embedding'"
    ).fetchone()
    return int(row[0]) if row is not None else None
