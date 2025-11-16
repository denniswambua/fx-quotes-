# FX-Quotes

FX-Quotes is a Django-based foreign exchange microservice that fetches, caches, and serves currency rates while enforcing idempotent quote and transaction flows.

## Table of contents
- [Project overview](#project-overview)
- [Architecture summary](#architecture-summary)
- [Tech stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Local development workflow](#local-development-workflow)
- [Background workers and scheduling](#background-workers-and-scheduling)
- [Database seeding](#database-seeding)
- [Running tests](#running-tests)
- [Containerised setup](#containerised-setup)
- [API surface](#api-surface)
- [Operations and handover notes](#operations-and-handover-notes)
- [Known limitations](#known-limitations)
- [Assumptions](#assumptions)

## Project overview
- Provides RESTful endpoints for managing currencies, exchange rates, quotes, and settlements.
- Enforces idempotency on write operations via `Idempotency-Key` headers.
- Currently ships with support for USD, EUR, KES, and NGN.
- Periodically refreshes rates from the configured third-party FX provider and caches results for low-latency quote generation.

## Architecture summary

<img width="774" height="670" alt="fx-quotes drawio" src="https://github.com/user-attachments/assets/92391e31-2008-41b8-846e-81025d792edf" />

- **API layer (Django REST Framework):** Exposes `/api/currencies`, `/api/rates`, `/api/quotes`, and `/api/transactions` with request validation and response serialization.
- **Persistence:** PostgreSQL (or SQLite for local development) stores the core domain models (`Currency`, `Rate`, `Quote`, `Transaction`).
- **Caching & messaging:** Redis caches exchange rates and acts as the Celery broker/result backend.
- **Background processing:** Celery beat triggers `fetch_latest_exchange_rates`, which ingests third-party data, normalizes values, and upserts the latest rates.
- **External integration:** A configurable Exchange Rates API supplies authoritative pricing; requests are retried with backoff and cached to protect the upstream service.

## Tech stack
- Python 3.13
- Django 5 + Django REST Framework 3
- Celery 5 with Redis broker/result backend
- PostgreSQL 17 (SQLite supported for quick local runs)
- `uv` for dependency management and virtual environments
- Docker + Docker Compose (optional, recommended for parity)

## Prerequisites
- Python 3.13 with `uv` installed (`pip install uv` or follow [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)).
- Access to PostgreSQL (local or container) and Redis if running services outside Docker.
- Docker Engine and Docker Compose v2 for the containerised workflow.

## Configuration
Create a `.env` file in the repository root (Docker Compose already reads from it). Adjust hosts and credentials to mirror your environment:

```env
DEBUG=True
SECRET_KEY="replace-with-a-random-string"
ALLOWED_HOSTS=localhost,127.0.0.1
SQL_ENGINE=django.db.backends.postgresql
SQL_USER=dev_user
SQL_PASSWORD=dev_password
SQL_DATABASE=dev_db
SQL_HOST=localhost
SQL_PORT=5432
EXCHANGE_RATES_API_URL=https://api.exchangeratesapi.io/v1/latest
EXCHANGE_RATES_API_KEY=replace-with-valid-api-key
REDIS_URL=redis://localhost:6379/0
```

> When running inside Docker Compose, `SQL_HOST` should be `db` and `REDIS_URL` should target the `cache` service (`redis://cache:6379/0`).

## Local development workflow
1. Create and activate the virtual environment using `uv`:
   ```bash
   uv venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies and sync the locked versions:
   ```bash
   uv sync
   ```
3. Apply database migrations:
   ```bash
   uv run manage.py migrate
   ```
4. Seed reference data (see [Database seeding](#database-seeding)).
5. Start the development server:
   ```bash
   uv run manage.py runserver 0.0.0.0:8000
   ```

## Background workers and scheduling
Run the Celery worker and beat scheduler in separate terminals to enable rate refreshes and asynchronous processing:

```bash
# Terminal 1
uv run celery -A app worker --loglevel=info

# Terminal 2
uv run celery -A app beat --loglevel=info
```

Both commands rely on Redis (`REDIS_URL`) being available.

## Database seeding
Load the supported currencies fixture after migrations:

```bash
uv run manage.py loaddata app/fixtures/currencies.json
```

Re-run the command whenever you need to reset or extend the reference data.

## Running tests
Execute the Django test suite (includes DRF endpoint coverage and Celery task tests):

```bash
uv run manage.py test
```

Use `coverage run -m manage.py test` if you need coverage metrics.

## Containerised setup

### Docker Compose
```bash
docker compose up --build
```

Once the services are healthy, run migrations and seed data from another terminal:

```bash
docker compose exec web uv run manage.py migrate
docker compose exec web uv run manage.py loaddata app/fixtures/currencies.json
```

Celery worker and beat services are built into the Compose stack and start automatically when Redis and the database are available.

### Local Docker helper
`run.sh` builds the Docker image and starts a container that mounts your working directory for rapid iteration:

```bash
./run.sh uv run manage.py runserver 0.0.0.0:8000
```

## API surface
| Endpoint | Methods | Description | Notes |
| --- | --- | --- | --- |
| `/health/` | `GET` | Liveness check returning `{ "status": "ok" }`. | - |
| `/api/currencies/` | `GET` | List supported currencies. | Paginated (`limit`/`offset`). |
| `/api/currencies/{code}/` | `GET` | Retrieve a single currency by code. | - |
| `/api/rates/` | `GET` | List latest exchange rates. | Paginated. |
| `/api/rates/{id}/` | `GET` | Retrieve a specific rate record. | - |
| `/api/quotes/` | `GET`, `POST` | List quotes or create a new quote. | `POST` requires `Idempotency-Key`; response returns rate, converted amount, and expiry. |
| `/api/quotes/{id}/` | `GET` | Retrieve a quote. | - |
| `/api/transactions/` | `GET`, `POST` | List transactions or create one from a quote. | `POST` requires `Idempotency-Key`; validates quote expiry, amount parity, and duplicate submissions. |
| `/api/transactions/{id}/` | `GET` | Retrieve a transaction. | - |

### Example requests

**Fetch rates**

```bash
curl -X GET "http://localhost:8000/api/rates/?limit=2" \
     -H "Accept: application/json"
```

```json
{
  "count": 12,
  "next": "http://localhost:8000/api/rates/?limit=2&offset=2",
  "previous": null,
  "results": [
    {
      "id": 42,
      "base_currency": "EUR",
      "target_currency": "USD",
      "rate": "1.1627",
      "timestamp": "2025-11-15T08:00:00Z"
    },
    {
      "id": 43,
      "base_currency": "EUR",
      "target_currency": "KES",
      "rate": "150.3223",
      "timestamp": "2025-11-15T08:00:00Z"
    }
  ]
}
```

**Create a quote**

```bash
curl -X POST "http://localhost:8000/api/quotes/" \
     -H "Content-Type: application/json" \
     -H "Idempotency-Key: quote-request-001" \
     -d '{
           "from_currency": "EUR",
           "to_currency": "USD",
           "amount": "100.0000"
         }'
```

```json
{
  "id": 77,
  "from_currency": "EUR",
  "to_currency": "USD",
  "amount": "100.0000",
  "converted_amount": "116.2700",
  "rate": "1.1627",
  "timestamp": "2025-11-15T08:05:00Z",
  "expiry_timestamp": "2025-11-15T08:06:00Z"
}
```

**Create a transaction**

```bash
curl -X POST "http://localhost:8000/api/transactions/" \
     -H "Content-Type: application/json" \
     -H "Idempotency-Key: txn-request-001" \
     -d '{
           "quote": 77,
           "amount": "100.0000"
         }'
```

```json
{
  "id": 211,
  "quote": 77,
  "amount": "100.0000",
  "timestamp": "2025-11-15T08:05:30Z"
}
```

## Operations and handover notes
- **Secrets management:** Rotate `SECRET_KEY` and external API keys per environment. Avoid committing `.env` files.
- **Migrations:** Run `uv run manage.py migrate` (or the Docker equivalent) before each deployment.
- **Scheduled jobs:** Ensure Celery beat is running; the default schedule lives in `app/tasks.py` and expects Redis availability.
- **Monitoring & logging:** Django logs requests to stdout, Celery logs to stdout as well—ship these to your logging solution in production.
- **Scale-out considerations:** The application is stateless; scale the web and worker containers horizontally once Redis and PostgreSQL are sized appropriately.

## Known limitations
- Historical exchange rates are not exposed; only the latest rates are stored and served.
- Transactions are processed synchronously; introducing asynchronous settlement and queue-based retries is a recommended next step.
- Rate ingestion depends on a single upstream provider; add redundancy for higher availability.

## Assumptions
- Consumers provide valid ISO 4217 currency codes.
- Network access to the third-party exchange rates API is stable in the target deployment environments.
