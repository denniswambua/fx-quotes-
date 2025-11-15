# FX-Quotes
Foreign exchange micro service in python/django.

Supports the following currencies:
- USD
- EUR
- KES
- NGN

## Setup and running
### Define your environment variable in .env

```
DEBUG=True
SECRET_KEY={define a very random secret}
ALLOWED_HOSTS=localhost,127.0.0.1
SQL_ENGINE=django.db.backends.postgresql
SQL_USER=dev_user
SQL_PASSWORD=dev_password
SQL_DATABASE=dev_db
SQL_HOST=db
SQL_PORT=5432
EXCHANGE_RATES_API_URL=http://api.exchangeratesapi.io/v1/latest
EXCHANGE_RATES_API_KEY={valid api key please}
```

The project uses uv to run commands and manage dependencies.
On the project root,
```
uv venv .venv
uv sync 
uv run manage.py migrate 
uv run manage.py loaddata app/fixture/currencies.json
uv rum manage.py runserver
```

### Using Docker 

```
docker-compose up --build
```

On another shell run to setup the database.

```
docker-compose exec web uv run manage.py migrate
docker-compose exec web uv run manage.py loaddata app/fixture/currencies.json
```

Next, load the supported currencies

```
docker-compose exec web uv run manage.py loaddata app/fixture/currencies.json
```

## Design approach and key decisions
### High-level system design
- **API Layer (Django REST Framework):** Exposes `/api/currencies`, `/api/rates`, `/api/quotes`, and `/api/transactions` endpoints; request validation and serialization handled by DRF viewsets/serializers.
- **Persistence:** PostgreSQL (or SQLite for local development) stores core domain models—`Currency`, `Rate`, `Quote`, and `Transaction`—providing transactional consistency.
- **Caching & Messaging:** Redis powers result caching for exchange rates and acts as the Celery broker/result backend to decouple background processing from request handling.
- **Background Processing (Celery):** A Celery beat scheduler triggers `fetch_latest_exchange_rates`, which calls the third-party FX provider, normalizes responses, and upserts the latest `Rate` records.
- **External Integrations:** Exchange rates API supplies authoritative pricing; responses are retried with exponential backoff and cached for fast quote generation.
- **Data Flow Example:**
  1. Client submits `POST /api/quotes` with currencies and amount.
  2. Service fetches the appropriate `Rate` (from cache, falling back to DB) or derives it via base-currency conversion.
  3. Quote is persisted with expiry metadata and returned to the client along with computed `converted_amount`.
  4. Downstream clients confirm settlement through `POST /api/transactions`, enforcing quote validity and amount parity.

## Known limitations
- No historical rate data
## Any assumptions you made
