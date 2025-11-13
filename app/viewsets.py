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
    serializer_class = CurrencySerializer
    queryset = Currency.objects.all()


class RateViewSet(
    mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    serializer_class = RateSerializer
    queryset = Rate.objects.all()


class QuoteViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = QuoteSerializer
    queryset = Quote.objects.all()


class TransactionViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = TransactionSerializer
    queryset = Transaction.objects.all()
