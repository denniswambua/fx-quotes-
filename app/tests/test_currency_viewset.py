from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import Currency


class CurrencyViewSetTests(APITestCase):
    def setUp(self):
        self.list_url = reverse("currency-list")

    def _detail_url(self, pk: str) -> str:
        return reverse("currency-detail", args=[pk])

    def test_create_currency(self):
        payload = {
            "currency_code": "USD",
            "currency_name": "US Dollar",
            "decimal_places": 2,
            "enabled": True,
        }

        response = self.client.post(self.list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Currency.objects.filter(currency_code="USD").exists())
        self.assertEqual(response.data["currency_name"], "US Dollar")

    def test_list_currencies(self):
        Currency.objects.create(
            currency_code="USD", currency_name="US Dollar", decimal_places=2
        )
        Currency.objects.create(
            currency_code="EUR", currency_name="Euro", decimal_places=2
        )

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertCountEqual(
            [item["currency_code"] for item in response.data],
            ["USD", "EUR"],
        )

    def test_retrieve_currency(self):
        Currency.objects.create(
            currency_code="USD", currency_name="US Dollar", decimal_places=2
        )

        response = self.client.get(self._detail_url("USD"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["currency_code"], "USD")
        self.assertEqual(response.data["currency_name"], "US Dollar")

    def test_update_currency(self):
        Currency.objects.create(
            currency_code="USD", currency_name="US Dollar", decimal_places=2
        )

        payload = {
            "currency_code": "USD",
            "currency_name": "United States Dollar",
            "decimal_places": 4,
            "enabled": False,
        }

        response = self.client.put(self._detail_url("USD"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        currency = Currency.objects.get(currency_code="USD")
        self.assertEqual(currency.currency_name, "United States Dollar")
        self.assertEqual(currency.decimal_places, 4)
        self.assertFalse(currency.enabled)

    def test_delete_currency(self):
        Currency.objects.create(
            currency_code="USD", currency_name="US Dollar", decimal_places=2
        )

        response = self.client.delete(self._detail_url("USD"))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Currency.objects.filter(currency_code="USD").exists())
