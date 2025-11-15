from rest_framework import viewsets, mixins

from app.serializers import (
    CurrencySerializer,
    RateSerializer,
    QuoteSerializer,
    TransactionSerializer,
)
from app.models import Currency, Rate, Quote, Transaction

"""
       Currency endpoint, 
       Lists and Retireves supported Currency.
       To insert other currencies use management commands.
"""


class CurrencyViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Read-only access to supported currencies.

    Example request:
        GET /api/currencies/?limit=2

    Example response (200):
        {
            "count": 42,
            "next": "https://api.example.com/api/currencies/?limit=2&offset=2",
            "previous": null,
            "results": [
                {
                    "currency_code": "USD",
                    "currency_name": "US Dollar",
                    "decimal_places": 2,
                    "enabled": true
                }
            ]
        }
    """
    serializer_class = CurrencySerializer
    queryset = Currency.objects.all()


class RateViewSet(
    mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    """Expose the latest exchange rates between currencies.

    Example request:
        GET /api/rates/?limit=2

    Example response (200):
        {
            "count": 12,
            "next": "https://api.example.com/api/rates/?limit=2&offset=2",
            "previous": null,
            "results": [
                {
                    "id": 15,
                    "base_currency": "USD",
                    "target_currency": "EUR",
                    "rate": "0.9200",
                    "timestamp": "2025-11-10T12:30:00Z"
                }
            ]
        }
    """
    serializer_class = RateSerializer
    queryset = Rate.objects.all()


class QuoteViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Create and read currency conversion quotes for transactions.

    Example request:
        POST /api/quotes/
        {
            "from_currency": "USD",
            "to_currency": "EUR",
            "amount": "100.0000"
        }

    Example response (201):
        {
            "id": 7,
            "from_currency": "USD",
            "to_currency": "EUR",
            "amount": "100.0000",
            "converted_amount": "92.0000",
            "rate": "0.9200",
            "timestamp": "2025-11-10T12:30:00Z",
            "expiry_timestamp": "2025-11-10T12:31:00Z"
        }
    """
    serializer_class = QuoteSerializer
    queryset = Quote.objects.all()


class TransactionViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Record and view settlement transactions generated from quotes.

    Example request:
        POST /api/transactions/
        {
            "quote": 7,
            "amount": "100.0000"
        }

    Example response (201):
        {
            "id": 21,
            "quote": 7,
            "amount": "100.0000",
            "timestamp": "2025-11-10T12:35:00Z"
        }
    """
    serializer_class = TransactionSerializer
    queryset = Transaction.objects.select_related()
