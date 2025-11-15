from datetime import timedelta

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import Currency, Quote, Rate


class QuoteViewSetTests(APITestCase):
    def setUp(self):
        self.from_currency = Currency.objects.create(
            currency_code="USD", currency_name="US Dollar", decimal_places=2
        )
        self.to_currency = Currency.objects.create(
            currency_code="EUR", currency_name="Euro", decimal_places=2
        )
        self.list_url = reverse("quote-list")
        Rate.objects.create(
            base_currency=self.from_currency,
            target_currency=self.to_currency,
            rate="0.8500",
            timestamp=timezone.now(),
        )

    def _detail_url(self, pk: int) -> str:
        return reverse("quote-detail", args=[pk])

    def test_create_quote(self):
        payload = {
            "from_currency": self.from_currency.currency_code,
            "to_currency": self.to_currency.currency_code,
            "amount": "100.0000",
        }

        response = self.client.post(self.list_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["amount"], "100.0000")
        self.assertIn("converted_amount", response.data)
        self.assertEqual(response.data["converted_amount"], "85.0000")
        self.assertIn("rate", response.data)
        self.assertEqual(response.data["rate"], "0.8500")
        self.assertIn("timestamp", response.data)
        self.assertIn("expiry_timestamp", response.data)
        quote = Quote.objects.get(pk=response.data["id"])
        self.assertEqual(str(quote.amount), "100.0000")
        self.assertEqual(str(quote.converted_amount), "85.0000")
        self.assertEqual(str(quote.rate), "0.8500")
        self.assertEqual(quote.from_currency, self.from_currency)
        self.assertEqual(quote.to_currency, self.to_currency)
        self.assertTrue(
            quote.expiry_timestamp - quote.timestamp
            < timedelta(seconds=settings.QUOTES_EXPIRY_SECONDS),
        )

    def test_create_quote_without_available_rate(self):
        Rate.objects.all().delete()

        cache.clear()
        payload = {
            "from_currency": self.from_currency.currency_code,
            "to_currency": self.to_currency.currency_code,
            "amount": "100.0000",
        }

        response = self.client.post(self.list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("amount", response.data)
        self.assertNotIn("timestamp", response.data)
        self.assertNotIn("expiry_timestamp", response.data)

    def test_list_quotes(self):
        Quote.objects.create(
            from_currency=self.from_currency,
            to_currency=self.to_currency,
            converted_amount="100.0000",
            amount="100.0000",
        )
        Quote.objects.create(
            from_currency=self.to_currency,
            to_currency=self.from_currency,
            converted_amount="200.0000",
            amount="200.0000",
        )

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_list_quotes_with_pagination(self):
        for index in range(5):
            Quote.objects.create(
                from_currency=self.from_currency,
                to_currency=self.to_currency,
                converted_amount=f"{100 + index}.0000",
                amount=f"{100 + index}.0000",
            )

        response = self.client.get(self.list_url, {"limit": 2, "offset": 1})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 5)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])
        self.assertIsNotNone(response.data["previous"])

    def test_retrieve_quote(self):
        quote = Quote.objects.create(
            from_currency=self.from_currency,
            to_currency=self.to_currency,
            converted_amount="100.0000",
            amount="100.0000",
        )

        response = self.client.get(self._detail_url(quote.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["amount"], "100.0000")
        self.assertEqual(response.data["converted_amount"], "100.0000")

    def test_update_quote(self):
        quote = Quote.objects.create(
            from_currency=self.from_currency,
            to_currency=self.to_currency,
            converted_amount="100.0000",
            amount="100.0000",
        )

        response = self.client.patch(
            self._detail_url(quote.pk), {"amount": "250.0000"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        quote.refresh_from_db()
        self.assertNotEqual(str(quote.amount), "250.0000")

    def test_delete_quote(self):
        quote = Quote.objects.create(
            from_currency=self.from_currency,
            to_currency=self.to_currency,
            converted_amount="100.0000",
            amount="100.0000",
        )

        response = self.client.delete(self._detail_url(quote.pk))

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Quote.objects.filter(pk=quote.pk).exists())
