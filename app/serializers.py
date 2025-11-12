from rest_framework import serializers
from app.models import Currency, Rate, Quote, Transaction


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency


class RateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rate


class QuoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quote


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
