# Contributing to Datum

Thanks for your interest. This guide covers the development setup, the house rules that keep the
design honest, and what a good contribution looks like.

## Development setup

Follow [`docs/SETUP.md`](docs/SETUP.md) to get Python 3.11+, PostgreSQL 17 with pgvector, and the
package installed. For development, install the dev and embed extras and run the suite against a
scratch database:

```bash
pip install -e '.[dev,embed]'
export DATUM_PG_DSN="postgresql://localhost/datum_dev"   # a SCRATCH database
createdb datum_dev && psql -d datum_dev -c "CREATE EXTENSION IF NOT EXISTS vector;"
python -m pytest -q
```

> [!WARNING]
> The suite truncates whatever `DATUM_PG_DSN` points at. Never point it at a database with real data.

## House rules

These are not bureaucracy. They are the specific disciplines that kept this project correct.

1. **Test against a real PostgreSQL, not a mock.** Anything touching transactions, isolation,
   ordering, or the compare-and-set path is only meaningfully tested against a real database.
2. **New physical operators must pass the conformance suite before they register.** Run it directly
   while developing:
   ```python
   from datum import ConformanceSuite
   report = ConformanceSuite.run(MyOperator())
   assert report.passed, report.failures
   ```
   The suite checks filter algebra, the score contract, tenancy fail-closed, and entitlement
   staleness. The registry enforces the same gate at runtime.
3. **The kernel is version-frozen.** The top-level `__all__` in `src/datum/__init__.py` is a budgeted
   public surface. Adding a top-level symbol is a deliberate change with a numbered entry in
   [`docs/decisions.md`](docs/decisions.md).
4. **Record every deviation from the spec in `docs/decisions.md`,** numbered, with the reasoning.
5. **Degrade loudly, never silently.** If a capability is unavailable, warn clearly about what is off
   and what it costs. Do not quietly fall back to a lesser path.
6. **No fabricated numbers** in docs, the README, or the paper. Predicted figures are labeled as
   templates until measured.

See [`LEARNING.md`](LEARNING.md) for the longer story behind these rules.

## Submitting a change

1. Create a branch from `main`.
2. Keep the change focused. If it spans several concerns, split it.
3. Add or update tests. If you change retrieval behavior, add a case to the regression set.
4. Run `python -m pytest -q` and make it green against a real Postgres.
5. Open a pull request that explains the what and the why, and links any relevant decision entry.

## Reporting bugs and asking questions

- Bugs and feature requests: open an issue with steps to reproduce and your environment.
- Questions and ideas: open a discussion.
- Security issues: do not open a public issue. See [`SECURITY.md`](SECURITY.md).
