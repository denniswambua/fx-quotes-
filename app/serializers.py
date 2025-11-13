from django.db import IntegrityError, transaction as db_transaction
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
            "rate",
        ]
        read_only_fields = ["timestamp", "expiry_timestamp", "rate"]

    def create(self, validated_data):
        original_amount = validated_data["amount"]
        from_currency = validated_data["from_currency"]
        to_currency = validated_data["to_currency"]

        try:
            converted_amount, rate_used = convert_currency(
                original_amount,
                from_currency.currency_code,
                to_currency.currency_code,
                return_rate=True,
            )
        except ValueError as exc:
            raise serializers.ValidationError({"amount": str(exc)}) from exc

        validated_data["amount"] = converted_amount
        validated_data["rate"] = rate_used
        return Quote.objects.create(**validated_data)


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = "__all__"

    def validate(self, attrs):
        quote = attrs.get("quote") or getattr(self.instance, "quote", None)
        amount = attrs.get("amount") or getattr(self.instance, "amount", None)
        if quote and quote.expiry_timestamp <= timezone.now():
            raise serializers.ValidationError({"quote": "Quote has expired."})

        if self.instance is None and quote and amount:
            if Transaction.objects.filter(quote=quote, amount=amount).exists():
                raise serializers.ValidationError(
                    {
                        "non_field_errors": [
                            "A transaction for this quote and amount already exists."
                        ]
                    }
                )
        return attrs

    def create(self, validated_data):
        try:
            with db_transaction.atomic():
                return super().create(validated_data)
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "A transaction for this quote and amount already exists."
                    ]
                }
            ) from exc