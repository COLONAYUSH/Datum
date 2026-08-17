#!/usr/bin/env python3
"""Run one adversarial stress PDF through Datum end to end.

Ingests the PDF into a SCRATCH Postgres database with the repository's
committed defaults (`Corpus.open(dsn, image_ocr=True)`), then runs every
question's query verbatim through `Corpus.search` and writes the top-5 hit
contents in the results-JSON format that score.py consumes:

    {"Q01": ["passage text 1", ..., "passage text 5"], ...}

The database must be a scratch database created for this run, e.g.:

    createdb datum_stress_a
    psql -d datum_stress_a -c "CREATE EXTENSION IF NOT EXISTS vector;"

Usage:
    python run_datum.py --dsn postgresql://localhost/datum_stress_a \
        --pdf document-a.pdf --questions questions-a.json \
        --out datum-results-a.json [--skip-ingest]

Ingest takes several minutes on CPU: the image-OCR pass renders pages at
288 dpi and runs up to three OCR engines plus a translation model over image
regions. Prefix with `caffeinate` on macOS so the machine does not sleep.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dsn", required=True,
                        help="Postgres DSN of a SCRATCH database (e.g. "
                             "postgresql://localhost/datum_stress_a)")
    parser.add_argument("--pdf", required=True, help="path to the stress PDF")
    parser.add_argument("--questions", required=True,
                        help="questions-a.json / questions-b.json")
    parser.add_argument("--out", required=True,
                        help="where to write the results JSON")
    parser.add_argument("--namespace", default="tenant:stress",
                        help="tenant namespace (default: tenant:stress)")
    parser.add_argument("--top-k", type=int, default=5,
                        help="how many hit contents to record per query (default 5)")
    parser.add_argument("--skip-ingest", action="store_true",
                        help="reuse an already-ingested scratch db; only run the queries")
    args = parser.parse_args()

    # Never touch the real corpus: refuse the project's main database.
    if args.dsn.rstrip("/").endswith("/datum"):
        parser.error("refusing to run against the main 'datum' database — "
                     "create a scratch db (e.g. datum_stress_a) instead")

    from datum.corpus import Corpus
    from datum.kernel.principal import Principal

    pdf_path = Path(args.pdf)
    if not args.skip_ingest and not pdf_path.is_file():
        parser.error(f"PDF not found: {pdf_path}")

    with open(args.questions, encoding="utf-8") as fh:
        questions = json.load(fh)["questions"]

    print(f"[run_datum] opening corpus at {args.dsn} (image_ocr=True)", flush=True)
    corpus = Corpus.open(args.dsn, image_ocr=True)
    try:
        if not args.skip_ingest:
            print(f"[run_datum] ingesting {pdf_path.name} — this takes several "
                  f"minutes (288 dpi render + OCR + translation gloss)", flush=True)
            t0 = time.time()
            n = corpus.ingest_file(
                str(pdf_path),
                Principal(id="ing", namespace=args.namespace),
                source_id=pdf_path.name,
            )
            print(f"[run_datum] ingested {n} records in {time.time() - t0:.0f}s",
                  flush=True)

        querier = Principal(id="q", namespace=args.namespace)
        results: dict[str, list[str]] = {}
        for question in questions:
            qid, query = question["id"], question["query"]
            t0 = time.time()
            evidence = corpus.search(query, principal=querier)
            contents = [hit.content for hit in evidence.hits[: args.top_k]]
            results[qid] = contents
            print(f"[run_datum] {qid}: {len(contents)} hits "
                  f"({time.time() - t0:.1f}s) — {query[:60]}", flush=True)
    finally:
        corpus.close()

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    print(f"[run_datum] wrote {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
