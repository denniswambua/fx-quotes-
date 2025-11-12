from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import Currency, Quote, Transaction


class TransactionViewSetTests(APITestCase):
    def setUp(self):
        self.from_currency = Currency.objects.create(
            currency_code="USD", currency_name="US Dollar", decimal_places=2
        )
        self.to_currency = Currency.objects.create(
            currency_code="EUR", currency_name="Euro", decimal_places=2
        )
        self.quote = Quote.objects.create(
            from_currency=self.from_currency,
            to_currency=self.to_currency,
            amount="100.0000",
        )
        self.list_url = reverse("transaction-list")

    def _detail_url(self, pk: int) -> str:
        return reverse("transaction-detail", args=[pk])

    def test_create_transaction(self):
        payload = {
            "quote": self.quote.pk,
            "amount": "100.0000",
        }

        response = self.client.post(self.list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Transaction.objects.filter(pk=response.data["id"]).exists())

    def test_list_transactions(self):
        Transaction.objects.create(quote=self.quote, amount="100.0000")
        Transaction.objects.create(quote=self.quote, amount="150.0000")

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_retrieve_transaction(self):
        transaction = Transaction.objects.create(quote=self.quote, amount="100.0000")

        response = self.client.get(self._detail_url(transaction.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["amount"], "100.0000")

    def test_update_transaction(self):
        transaction = Transaction.objects.create(quote=self.quote, amount="100.0000")

        response = self.client.patch(
            self._detail_url(transaction.pk),
            {"state": Transaction.SUCCESS},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        transaction.refresh_from_db()
        self.assertEqual(transaction.state, Transaction.SUCCESS)

    def test_delete_transaction(self):
        transaction = Transaction.objects.create(quote=self.quote, amount="100.0000")

        response = self.client.delete(self._detail_url(transaction.pk))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Transaction.objects.filter(pk=transaction.pk).exists())
