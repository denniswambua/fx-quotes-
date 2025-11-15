from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from app.models import Currency, Rate
from app.tasks import _deserialize_timestamp, fetch_latest_exchange_rates


class FetchLatestExchangeRatesTaskTests(TestCase):
    def setUp(self):
        self.base_currency_code = settings.EXCHANGE_RATES_BASE_CURRENCY.upper()
        self.base_currency = Currency.objects.create(
            currency_code=self.base_currency_code,
            currency_name="Base Currency",
            decimal_places=4,
            enabled=True,
        )
        self.target_currency = Currency.objects.create(
            currency_code="USD",
            currency_name="US Dollar",
            decimal_places=4,
            enabled=True,
        )

    @override_settings(CELERY_ALWAYS_EAGER=True)
    @patch("app.tasks._fetch_payload")
    def test_fetch_latest_exchange_rates_updates_rates_with_mocked_api(
        self, mock_fetch_payload
    ):
        timestamp_value = 1_700_000_000
        mock_fetch_payload.return_value = {
            "timestamp": timestamp_value,
            "rates": {
                "USD": "0.8500",
                "JPY": "110.0000",
            },
        }

        fetch_latest_exchange_rates.run()

        mock_fetch_payload.assert_called_once()
        called_url = mock_fetch_payload.call_args.args[0]
        self.assertIn(f"base={self.base_currency_code}", called_url)
        self.assertIn("symbols=USD", called_url)

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


class DeserializeTimestampTests(SimpleTestCase):
    def test_returns_aware_datetime_from_epoch_timestamp(self):
        payload = {"timestamp": 1_700_000_000}

        result = _deserialize_timestamp(payload)

        self.assertEqual(result, datetime.fromtimestamp(1_700_000_000, tz=dt_timezone.utc))

    def test_parses_date_string_when_timestamp_missing(self):
        payload = {"date": "2025-11-15"}

        result = _deserialize_timestamp(payload)

        expected = timezone.make_aware(datetime(2025, 11, 15))
        self.assertEqual(result, expected)

    def test_falls_back_to_current_time(self):
        fallback = timezone.make_aware(datetime(2025, 1, 1, 12, 0, 0))
        with patch("app.tasks.timezone.now", return_value=fallback):
            result = _deserialize_timestamp({})

        self.assertEqual(result, fallback)
