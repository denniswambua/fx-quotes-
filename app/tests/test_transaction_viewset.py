import json
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import Currency, Quote, Transaction


class TransactionViewSetTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.from_currency = Currency.objects.create(
            currency_code="USD", currency_name="US Dollar", decimal_places=2
        )
        self.to_currency = Currency.objects.create(
            currency_code="EUR", currency_name="Euro", decimal_places=2
        )
        self.quote = Quote.objects.create(
            from_currency=self.from_currency,
            to_currency=self.to_currency,
            converted_amount="100.0000",
            amount="100.0000",
        )
        self.list_url = reverse("transaction-list")

    def _detail_url(self, pk: int) -> str:
        return reverse("transaction-detail", args=[pk])

    def _json(self, response):
        if hasattr(response, "data"):
            return response.data
        return json.loads(response.content)

    def test_create_transaction(self):
        payload = {
            "quote": self.quote.pk,
            "amount": "100.0000",
        }

        with self.assertLogs("app.serializers", level="INFO") as captured:
            response = self.client.post(
                self.list_url,
                payload,
                format="json",
                HTTP_IDEMPOTENCY_KEY="txn-create-1",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = self._json(response)
        self.assertTrue(Transaction.objects.filter(pk=body["id"]).exists())
        self.assertTrue(
            any("Transaction created" in message for message in captured.output)
        )

    def test_list_transactions(self):
        other_quote = Quote.objects.create(
            from_currency=self.from_currency,
            to_currency=self.to_currency,
            converted_amount="150.0000",
            amount="150.0000",
        )
        Transaction.objects.create(quote=self.quote, amount="100.0000")
        Transaction.objects.create(quote=other_quote, amount="150.0000")

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_retrieve_transaction(self):
        transaction = Transaction.objects.create(quote=self.quote, amount="100.0000")

        response = self.client.get(self._detail_url(transaction.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["amount"], "100.0000")

    def test_update_transaction(self):
        transaction = Transaction.objects.create(quote=self.quote, amount="100.0000")

        response = self.client.patch(
            self._detail_url(transaction.pk),
            {"amount": "120.0000"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        transaction.refresh_from_db()
        self.assertEqual(str(transaction.amount), "100.0000")

    def test_delete_transaction(self):
        transaction = Transaction.objects.create(quote=self.quote, amount="100.0000")

        response = self.client.delete(self._detail_url(transaction.pk))

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Transaction.objects.filter(pk=transaction.pk).exists())

    def test_create_transaction_with_expired_quote(self):
        self.quote.timestamp = timezone.now() - timedelta(
            seconds=settings.QUOTES_EXPIRY_SECONDS + 1
        )
        self.quote.expiry_timestamp = self.quote.timestamp + timedelta(
            seconds=settings.QUOTES_EXPIRY_SECONDS
        )
        self.quote.save(update_fields=["timestamp", "expiry_timestamp"])

        payload = {
            "quote": self.quote.pk,
            "amount": "100.0000",
        }

        with self.assertLogs("app.serializers", level="WARNING") as captured:
            response = self.client.post(
                self.list_url,
                payload,
                format="json",
                HTTP_IDEMPOTENCY_KEY="txn-expired",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        body = self._json(response)
        self.assertIn("quote", body)
        self.assertEqual(body["quote"][0], "Quote has expired.")
        self.assertTrue(
            any("Attempted transaction on expired quote" in message for message in captured.output)
        )

    def test_create_transaction_with_amount_mismatch(self):
        payload = {
            "quote": self.quote.pk,
            "amount": "150.0000",
        }

        response = self.client.post(
            self.list_url,
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="txn-mismatch",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        body = self._json(response)
        self.assertIn("amount", body)
        self.assertEqual(
            body["amount"][0],
            "Transaction amount must match the original quoted amount.",
        )

    def test_create_duplicate_transaction(self):
        payload = {"quote": self.quote.pk, "amount": 100.00}
        with self.assertLogs("app.serializers", level="INFO") as captured:
            response = self.client.post(
                self.list_url,
                payload,
                format="json",
                HTTP_IDEMPOTENCY_KEY="txn-dup",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Transaction.objects.filter(pk=self._json(response)["id"]).exists())
        self.assertTrue(
            any("Transaction created" in message for message in captured.output)
        )

        cached_response = self.client.post(
            self.list_url,
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="txn-dup",
        )

        self.assertEqual(cached_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self._json(cached_response), self._json(response))

        with self.assertLogs("app.serializers", level="WARNING") as duplicate_logs:
            duplicate_response = self.client.post(
                self.list_url,
                payload,
                format="json",
                HTTP_IDEMPOTENCY_KEY="txn-dup-second",
            )

        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)
        duplicate_body = self._json(duplicate_response)
        self.assertIn("non_field_errors", duplicate_body)
        self.assertTrue(
            any("Duplicate transaction detected" in message for message in duplicate_logs.output)
        )

    def test_create_transaction_requires_idempotency_header(self):
        payload = {
            "quote": self.quote.pk,
            "amount": "100.0000",
        }

        response = self.client.post(self.list_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self._json(response)["error"], "Idempotency-Key header required")

    def test_create_transaction_returns_cached_response_for_same_key(self):
        payload = {
            "quote": self.quote.pk,
            "amount": "100.0000",
        }

        key = "txn-idempotent-key"
        first = self.client.post(
            self.list_url,
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        first_body = self._json(first)
        initial_count = Transaction.objects.count()

        second = self.client.post(
            self.list_url,
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self._json(second), first_body)
        self.assertEqual(Transaction.objects.count(), initial_count)
