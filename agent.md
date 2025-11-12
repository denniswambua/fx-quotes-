# Agent Context

## Project Overview
- Django 5.2 + Django REST Framework service for managing currencies, rates, quotes (with expiry), and transactions.
- `app.viewsets` exposes CRUD endpoints via router at `api/currencies`, `api/rates`, `api/quotes`, and `api/transactions`.

## Key Artifacts
- CRUD API tests located in `app/tests/` covering `CurrencyViewSet`, `RateViewSet`, `QuoteViewSet`, and `TransactionViewSet` using `APITestCase`.
- Currency fixture `app/fixtures/currencies.json` seeds USD, EUR, KES, and NGN records.

## Testing Status
- Django test runs were previously cancelled at user request; rerun `python3 manage.py test app.tests` when validation is needed.
