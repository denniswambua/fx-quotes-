from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase

from app.models import Currency, Rate
from app.tasks import fetch_latest_exchange_rates


class FetchLatestExchangeRatesTaskTests(TestCase):
    def setUp(self):
        self.base_currency_code = settings.EXCHANGE_RATES_BASE_CURRENCY.upper()
        self.base_currency = Currency.objects.create(
            currency_code=self.base_currency_code,
            currency_name="Base Currency",
            decimal_places=2,
            enabled=True,
        )
        self.target_currency = Currency.objects.create(
            currency_code="EUR",
            currency_name="Euro",
            decimal_places=2,
            enabled=True,
        )

    @patch("app.tasks._fetch_payload")
    def test_fetch_latest_exchange_rates_updates_rates_with_mocked_api(self, mock_fetch_payload):
        timestamp_value = 1_700_000_000
        mock_fetch_payload.return_value = {
            "timestamp": timestamp_value,
            "rates": {
                "EUR": "0.8500",
                "JPY": "110.0000",
            },
        }

        fetch_latest_exchange_rates.run()

        mock_fetch_payload.assert_called_once()
        called_url = mock_fetch_payload.call_args.args[0]
        self.assertIn(f"base={self.base_currency_code}", called_url)
        self.assertIn("symbols=EUR", called_url)

        rate = Rate.objects.get(
            base_currency=self.base_currency,
            target_currency=self.target_currency,
        )
        self.assertEqual(rate.rate, Decimal("0.8500"))
        self.assertEqual(
            rate.timestamp,
            datetime.fromtimestamp(timestamp_value, tz=dt_timezone.utc),
        )
        self.assertFalse(
            Rate.objects.filter(target_currency__currency_code="JPY").exists()
        )
