# weather-etl-mysql

A small ETL pipeline that pulls historical daily weather for a handful of
cities from the free [Open-Meteo](https://open-meteo.com/) archive API,
flattens and validates it with pandas, and loads it into MySQL.

Built as a weekend project to demonstrate a realistic extract → validate →
load pipeline: pagination, retries/timeouts, data quality checks, logging,
and an idempotent MySQL load.

## Architecture

```
src/extract.py    requests.Session with retry/backoff; chunks a date range
                  into pages and fetches one HTTP request per page
src/transform.py  flattens nested daily JSON into a tidy DataFrame and
                  validates it (required fields, types, ranges, duplicates)
src/load.py       upserts the clean DataFrame into MySQL
src/main.py       orchestrates extract -> transform -> validate -> load
```

### Pagination

Open-Meteo's archive endpoint doesn't use cursor/offset pagination — you
just pass a `start_date`/`end_date` and it returns everything in between.
To still demonstrate (and actually benefit from) pagination, a requested
date range is split into fixed-size chunks (`PAGE_SIZE_DAYS`, default 90
days) and each chunk is fetched as its own page/request. This keeps
individual responses small, lets retries apply per-chunk rather than
to the whole job, and would extend naturally to a true cursor-paginated
API by swapping `iter_date_pages` for a "follow the next link" loop.

### Retries and timeouts

`extract.build_session()` mounts an `HTTPAdapter` configured with a
`urllib3.util.retry.Retry` policy: 3 retries with exponential backoff,
retrying on 429/500/502/503/504. Every request also has an explicit
10 second timeout, so a hanging connection can't stall the pipeline
indefinitely.

### Validation

`transform.validate()` checks, in order:
1. all required columns are present (raises if not — this is a schema
   problem, not a data problem)
2. each field parses to the expected type (dates, numbers)
3. values fall in a physically plausible range (e.g. -90°C to 60°C,
   non-negative precipitation, max ≥ min)
4. duplicate `(city, date)` rows are dropped, keeping the first

Rows failing checks 2-4 are moved to a `rejected` DataFrame with a
`reason` column and logged, rather than silently dropped or crashing
the run.

### Loading

`load.py` upserts into MySQL with `INSERT ... ON DUPLICATE KEY UPDATE`,
keyed on a `UNIQUE (city, observation_date)` constraint (see
[`sql/schema.sql`](sql/schema.sql)). Re-running the pipeline over an
overlapping date range updates existing rows instead of erroring or
duplicating them.

### Logging

Logs go to both the console and a rotating file at `logs/etl.log`
(1MB per file, 3 backups), configured in
[`src/logging_config.py`](src/logging_config.py).

## Setup

Requires Python 3.9+ and Docker.

```bash
cp .env.example .env
docker compose up -d        # starts MySQL 8 and applies sql/schema.sql

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
python -m src.main                                   # defaults to 2023
python -m src.main --start-date 2023-06-01 --end-date 2023-06-30
```

## Tests

```bash
pytest
```

Tests mock all HTTP calls (`requests_mock`) and don't require MySQL or
network access — they cover date-chunk pagination, the retry adapter
configuration, JSON flattening, and each validation rule.

## Possible extensions

- Parameterise the city list and date range via a config file instead
  of editing `src/config.py`
- Add a `--dry-run` flag that validates without loading
- Swap the archive endpoint for Open-Meteo's live forecast endpoint and
  schedule the pipeline to run daily
