from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from app.models import Currency, Rate
from app.utils import convert_currency


class CurrencyConversionUtilsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.base_code = settings.EXCHANGE_RATES_BASE_CURRENCY.upper()
        self.base_currency = Currency.objects.create(
            currency_code=self.base_code,
            currency_name="Base Currency",
            decimal_places=4,
        )
        self.usd = Currency.objects.create(
            currency_code="USD",
            currency_name="Us Dollar",
            decimal_places=4,
        )
        self.gbp = Currency.objects.create(
            currency_code="GBP",
            currency_name="British Pound",
            decimal_places=4,
        )

        now = timezone.now()
        Rate.objects.create(
            base_currency=self.base_currency,
            target_currency=self.usd,
            rate=Decimal("0.9000"),
            timestamp=now,
        )
        Rate.objects.create(
            base_currency=self.base_currency,
            target_currency=self.gbp,
            rate=Decimal("0.8000"),
            timestamp=now,
        )

    def test_converts_with_direct_rate(self):
        result = convert_currency(Decimal("100"), self.base_code, "USD")
        self.assertEqual(result, Decimal("90.0000"))

    def test_converts_using_inverse_rate(self):
        result = convert_currency(Decimal("90"), "USD", self.base_code)
        self.assertEqual(result, Decimal("100.0000"))

    def test_converts_via_base_currency_when_no_direct_rate(self):
        result = convert_currency(Decimal("90"), "USD", "GBP")
        self.assertEqual(result, Decimal("80.0000"))

    def test_same_currency_returns_quantized_amount(self):
        result = convert_currency(Decimal("9.123456"), "USD", "USD")
        self.assertEqual(result, Decimal("9.1235"))

    def test_raises_when_missing_rate(self):
        Currency.objects.create(
            currency_code="JPY",
            currency_name="Japanese Yen",
            decimal_places=0,
        )

        with self.assertRaises(ValueError):
            convert_currency(Decimal("10"), "USD", "JPY")

    def test_raises_when_direct_rate_stale(self):
        stale_timestamp = timezone.now() - timedelta(
            seconds=settings.EXCHANGE_RATES_EXPIRY_SECONDS + 1
        )
        Rate.objects.filter(
            base_currency=self.base_currency, target_currency=self.usd
        ).update(timestamp=stale_timestamp, update_timestamp=stale_timestamp)

        with self.assertRaisesRegex(ValueError, "stale"):
            convert_currency(Decimal("100"), self.base_code, "USD")

    def test_raises_when_base_rate_stale(self):
        fresh_timestamp = timezone.now()
        Rate.objects.filter(
            base_currency=self.base_currency, target_currency=self.usd
        ).update(timestamp=fresh_timestamp, update_timestamp=fresh_timestamp)

        stale_timestamp = timezone.now() - timedelta(
            seconds=settings.EXCHANGE_RATES_EXPIRY_SECONDS + 5
        )
        Rate.objects.filter(
            base_currency=self.base_currency, target_currency=self.gbp
        ).update(timestamp=stale_timestamp, update_timestamp=stale_timestamp)

        with self.assertRaisesRegex(ValueError, "stale"):
            convert_currency(Decimal("90"), "USD", "GBP")
