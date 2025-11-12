from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import Currency, Rate


class RateViewSetTests(APITestCase):
    def setUp(self):
        self.base_currency = Currency.objects.create(
            currency_code="USD", currency_name="US Dollar", decimal_places=2
        )
        self.target_currency = Currency.objects.create(
            currency_code="EUR", currency_name="Euro", decimal_places=2
        )
        self.list_url = reverse("rate-list")

    def _detail_url(self, pk: int) -> str:
        return reverse("rate-detail", args=[pk])

    def test_create_rate(self):
        payload = {
            "base_currency": self.base_currency.currency_code,
            "target_currency": self.target_currency.currency_code,
            "rate": "1.1000",
            "timestamp": timezone.now().isoformat(),
        }

        response = self.client.post(self.list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Rate.objects.filter(
                base_currency=self.base_currency,
                target_currency=self.target_currency,
            ).exists()
        )

    def test_list_rates(self):
        Rate.objects.create(
            base_currency=self.base_currency,
            target_currency=self.target_currency,
            rate="1.1000",
            timestamp=timezone.now(),
        )
        Rate.objects.create(
            base_currency=self.target_currency,
            target_currency=self.base_currency,
            rate="0.9000",
            timestamp=timezone.now(),
        )

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_retrieve_rate(self):
        rate = Rate.objects.create(
            base_currency=self.base_currency,
            target_currency=self.target_currency,
            rate="1.1000",
            timestamp=timezone.now(),
        )

        response = self.client.get(self._detail_url(rate.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["rate"], "1.1000")

    def test_update_rate(self):
        rate = Rate.objects.create(
            base_currency=self.base_currency,
            target_currency=self.target_currency,
            rate="1.1000",
            timestamp=timezone.now(),
        )

        response = self.client.patch(
            self._detail_url(rate.pk), {"rate": "1.1500"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rate.refresh_from_db()
        self.assertEqual(str(rate.rate), "1.1500")

    def test_delete_rate(self):
        rate = Rate.objects.create(
            base_currency=self.base_currency,
            target_currency=self.target_currency,
            rate="1.1000",
            timestamp=timezone.now(),
        )

        response = self.client.delete(self._detail_url(rate.pk))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Rate.objects.filter(pk=rate.pk).exists())
