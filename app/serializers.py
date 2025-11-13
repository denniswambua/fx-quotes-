from django.utils import timezone
from rest_framework import serializers

from app.models import Currency, Rate, Quote, Transaction
from app.utils import convert_currency


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = "__all__"


class RateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rate
        fields = "__all__"


class QuoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quote
        fields = [
            "id",
            "from_currency",
            "to_currency",
            "amount",
            "timestamp",
            "expiry_timestamp",
        ]
        read_only_fields = ["timestamp", "expiry_timestamp"]

    def create(self, validated_data):
        original_amount = validated_data["amount"]
        from_currency = validated_data["from_currency"]
        to_currency = validated_data["to_currency"]

        try:
            converted_amount = convert_currency(
                original_amount,
                from_currency.currency_code,
                to_currency.currency_code,
            )
        except ValueError as exc:
            raise serializers.ValidationError({"amount": str(exc)}) from exc

        validated_data["amount"] = converted_amount
        return Quote.objects.create(**validated_data)


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = "__all__"

    def validate(self, attrs):
        quote = attrs.get("quote") or getattr(self.instance, "quote", None)
        if quote and quote.expiry_timestamp <= timezone.now():
            raise serializers.ValidationError({"quote": "Quote has expired."})

        return attrs
