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
### Requirements
- python3.13
- uv 
- docker (Optional)

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

<img width="774" height="670" alt="fx-quotes drawio" src="https://github.com/user-attachments/assets/92391e31-2008-41b8-846e-81025d792edf" />

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

### API endpoints
| Endpoint | Methods | Description | Notes |
| --- | --- | --- | --- |
| `/health/` | `GET` | Liveness check returning `{ "status": "ok" }`. | - |
| `/api/currencies/` | `GET` | List supported currencies. | Paginated (`limit`/`offset`). |
| `/api/currencies/{code}/` | `GET` | Retrieve a single currency by code. | - |
| `/api/rates/` | `GET` | List latest exchange rates. | Paginated. |
| `/api/rates/{id}/` | `GET` | Retrieve a specific rate record. | - |
| `/api/quotes/` | `GET`, `POST` | List quotes or create a new quote. | `POST` requires `Idempotency-Key` header; response includes rate, converted amount, and expiry. |
| `/api/quotes/{id}/` | `GET` | Retrieve a quote. | - |
| `/api/transactions/` | `GET`, `POST` | List transactions or create one from a quote. | `POST` requires `Idempotency-Key`; validates quote expiry, amount parity, and duplicate submissions. |
| `/api/transactions/{id}/` | `GET` | Retrieve a transaction. | - |

#### Example requests

**Fetch rates**

```bash
curl -X GET "http://localhost:8000/api/rates/?limit=2" \
     -H "Accept: application/json"
```

Sample response:

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

Sample response:

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

Sample response:

```json
{
  "id": 211,
  "quote": 77,
  "amount": "100.0000",
  "timestamp": "2025-11-15T08:05:30Z"
}
```

## Known limitations
- No historical rate data
## Any assumptions you made
