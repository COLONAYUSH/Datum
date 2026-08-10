# Setup guide

This walks you from a clean machine to a running Datum, ingesting and searching real documents. It
assumes no prior knowledge of the project. If a step fails, jump to [Troubleshooting](#troubleshooting).

There are three things to install: **Python 3.11+**, **PostgreSQL 17 with the pgvector extension**,
and **Datum itself**. That is the whole list. Datum uses Postgres for everything, so there is no
separate vector database or search cluster to run.

## 1. Prerequisites

### Python 3.11 or newer

Check what you have:

```bash
python3 --version
```

If it is older than 3.11, install a newer one. On macOS with Homebrew:

```bash
brew install python@3.12
```

### PostgreSQL 17

macOS with Homebrew:

```bash
brew install postgresql@17
brew services start postgresql@17     # starts Postgres and keeps it running
```

Confirm it is running and note the version:

```bash
psql postgres -c "SHOW server_version;"
```

Linux (Debian or Ubuntu): install `postgresql-17` from the PostgreSQL APT repository, then make sure
the service is started.

### pgvector (the vector extension)

Datum's semantic search stores embeddings in Postgres using the `vector` type from
[pgvector](https://github.com/pgvector/pgvector). Check whether it is already available:

```bash
psql postgres -tAc "SELECT default_version FROM pg_available_extensions WHERE name='vector';"
```

If that prints a version (for example `0.8.0`), you are set. If it prints nothing, install it. The
most reliable way, especially if you have more than one Postgres installed, is to build it against
the exact server you are running, so the extension lands where that server looks for it:

```bash
git clone --depth 1 --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector
make PG_CONFIG="$(which pg_config)"
make PG_CONFIG="$(which pg_config)" install
cd .. && rm -rf pgvector
```

> [!NOTE]
> Building from source needs a C compiler. On macOS run `xcode-select --install` once if you do not
> already have the command line tools. `make install` writes into your Homebrew Postgres tree and
> does not need `sudo`.

Homebrew also has a formula (`brew install pgvector`), but on a machine with multiple Postgres
versions it can build against the wrong one. The source build above avoids that.

## 2. Install Datum

Clone the repository and install it into a virtual environment. The `[embed]` extra pulls the
embedding model and the reranker, which is what turns on real semantic search.

```bash
git clone https://github.com/COLONAYUSH/Datum.git
cd Datum
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[embed]'
```

The first install downloads PyTorch and the sentence-transformers stack, so it is a few hundred
megabytes and takes a couple of minutes.

> [!NOTE]
> If you skip the `[embed]` extra, Datum still runs on BM25 and grep, and it will warn you that the
> dense semantic operator is turned off. Install `[embed]` for the full hybrid retrieval described in
> the README.

## 3. Create a database and turn on pgvector

Datum reads its connection string from the `DATUM_PG_DSN` environment variable. Point it at a
**scratch** database.

> [!WARNING]
> The test suite and `datum eval` **truncate** whatever database `DATUM_PG_DSN` points at. Always use
> a throwaway database, never one that holds data you care about.

```bash
export DATUM_PG_DSN="postgresql://localhost/datum_dev"
createdb datum_dev
psql -d datum_dev -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Optional but recommended: a stable secret so search result handles stay valid across restarts.
export DATUM_HIT_SIGNING_KEY="pick-any-stable-secret"
```

Datum creates its own tables on first use, so there is no migration step to run by hand.

## 4. Verify it works

Ingest the bundled example document and search it:

```bash
datum ingest ./docs/examples/runbook.md --source-id runbook --namespace tenant:acme
datum search "how do I roll back a deploy" --namespace tenant:acme
```

You should see a ranked hit from the "Rollback" section, with a status of `ok` and a sufficiency
score. The query shares almost no words with the source sentence, so a good result here confirms the
dense semantic operator is working, not just keyword matching.

Run the full test suite against your scratch database to confirm the whole system is healthy:

```bash
pip install -e '.[dev,embed]'
python -m pytest -q          # first run loads the models, so allow a few minutes
```

## 5. Use it from an AI agent (optional)

Datum ships as a Model Context Protocol server. Start it over stdio:

```bash
datum serve --namespace tenant:acme
```

See the [README](../README.md#use-it-from-an-agent-mcp) for a ready-to-paste MCP client
configuration (for example Claude Desktop).

## Troubleshooting

<details>
<summary><b>psql: could not connect to server</b></summary>

Postgres is not running. Start it (`brew services start postgresql@17` on macOS) and try again.
Confirm with `psql postgres -c "SELECT 1;"`.
</details>

<details>
<summary><b>ERROR: extension "vector" is not available</b></summary>

pgvector is not installed for the Postgres you are connected to. Follow
[step 1, pgvector](#pgvector-the-vector-extension). If you have more than one Postgres, make sure
`which pg_config` points at the same server `psql` connects to, then rebuild from source against it.
</details>

<details>
<summary><b>Search returns hits but they look keyword-only, or a UserWarning about no embedder</b></summary>

The dense operator is off because the embedding model is not installed. Install the extra:
`pip install -e '.[embed]'`. The warning names exactly what is missing.
</details>

<details>
<summary><b>The first search or test run hangs for a while</b></summary>

That is the embedding model and the reranker downloading from HuggingFace and loading into memory on
first use. It is a one-time cost per machine. Later runs read from the local cache.
</details>

<details>
<summary><b>A model download fails with a connection or SSL error</b></summary>

Your network is blocking HuggingFace. Set `HF_ENDPOINT` to a mirror your network allows, or pre-stage
the model cache on a machine that can reach HuggingFace and copy `~/.cache/huggingface` over.
</details>

<details>
<summary><b>I accidentally ran tests against the wrong database</b></summary>

The suite truncates its tables. Recreate a clean scratch database and re-point `DATUM_PG_DSN` at it.
Set `DATUM_PG_DSN` in your shell profile so it is never unset by accident.
</details>

## Where to go next

- `README.md` for the concepts, the API, and how retrieval works.
- `HANDOFF.md` for current status and the exact next steps.
- `LEARNING.md` for the lessons and gotchas from building this.
- `docs/decisions.md` for why the architecture is the way it is.
