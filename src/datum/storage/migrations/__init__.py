"""A hand-rolled, numbered SQL migration runner. No ORM, no migration
framework dependency — the plan's own description of this piece
(FRAMEWORK.md §Adoption path's "boring, inspectable" storage layer) is
satisfied by exactly this: plain numbered `.sql` files, applied in order,
tracked in a table this module creates on first run.

Numbering convention: files are named `NNNN_description.sql` with a
zero-padded four-digit prefix (`0001_wal.sql`, `0002_...`). `sorted()` over
the directory listing is correct *because* of that zero-padding — plain
lexicographic sort and numeric sort agree up to 9999 migrations, which is
adequate headroom without needing to parse the prefix as an int just to
sort correctly.
"""

from __future__ import annotations

from pathlib import Path

import psycopg

_MIGRATIONS_DIR = Path(__file__).parent

# Arbitrary but fixed 64-bit key for the advisory lock this module takes
# around an entire migration run. Six-plus agents/processes touching the
# same Postgres concurrently (this build's own multi-agent setup, or any
# multi-worker test run) could otherwise race two runners into applying
# the same migration twice, or one runner reading a half-created
# `schema_migrations` table another is still creating. A single
# session-scoped advisory lock, held for the run's duration and released
# automatically when the connection closes, makes the whole run mutually
# exclusive without needing a separate coordination service.
_MIGRATION_LOCK_KEY = 0x64617475_6D5F6D69  # "datu" "m_mi" as two 32-bit halves


def run_migrations(dsn: str) -> None:
    """Apply every not-yet-applied `NNNN_*.sql` file in this directory, in
    filename order, tracking progress in a `schema_migrations` table.

    Idempotent: running this twice against the same database applies
    nothing the second time and raises nothing either — a migration
    already recorded as applied is skipped, not re-run. This is what lets
    every module that depends on this schema (wal.py, and this package's
    own tests) call `run_migrations` unconditionally at setup time instead
    of tracking "have I already done this" themselves.
    """
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (_MIGRATION_LOCK_KEY,))
        try:
            _ensure_tracking_table(conn)
            applied = _applied_migrations(conn)
            for sql_path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
                name = sql_path.name
                if name in applied:
                    continue
                _apply_one(conn, sql_path)
        finally:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (_MIGRATION_LOCK_KEY,))


def _ensure_tracking_table(conn: psycopg.Connection) -> None:
    # Its own transaction, separate from any individual migration's, so a
    # later migration's failure can never roll back the fact that tracking
    # itself exists.
    with conn.transaction():
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename    TEXT PRIMARY KEY,
                applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )


def _applied_migrations(conn: psycopg.Connection) -> frozenset[str]:
    rows = conn.execute("SELECT filename FROM schema_migrations").fetchall()
    return frozenset(row[0] for row in rows)


def _apply_one(conn: psycopg.Connection, sql_path: Path) -> None:
    # Each migration's SQL and its own tracking-row insert commit together,
    # in one transaction: a migration that runs but whose completion never
    # gets recorded (crash between the two) is exactly the state that would
    # cause it to be silently re-run and fail on its own CREATE TABLE next
    # time, so they must not be split across separate commits.
    sql = sql_path.read_text()
    with conn.transaction():
        conn.execute(sql)
        conn.execute(
            "INSERT INTO schema_migrations (filename) VALUES (%s)",
            (sql_path.name,),
        )
