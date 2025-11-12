from datetime import timedelta
from django.db import models
from django.conf import settings


class Currency(models.Model):
    currency_code = models.CharField(primary_key=True, max_length=3)
    currency_name = models.CharField(max_length=255)
    decimal_places = models.SmallIntegerField(default=4)
    enabled = models.BooleanField(default=True)


class Rate(models.Model):
    base_currency = models.ForeignKey(
        Currency,
        related_name="%(app_label)s_%(class)s_ibase_related",
        on_delete=models.RESTRICT,
    )
    target_currency = models.ForeignKey(
        Currency,
        related_name="%(app_label)s_%(class)s_target_related",
        on_delete=models.RESTRICT,
    )
    rate = models.DecimalField(max_digits=10, decimal_places=4)
    timestamp = models.DateTimeField()


class Qoute(models.Model):
    from_currency = models.ForeignKey(
        Currency,
        related_name="%(app_label)s_%(class)s_from_related",
        on_delete=models.RESTRICT,
    )
    to_currency = models.ForeignKey(
        Currency,
        related_name="%(app_label)s_%(class)s_to_related",
        on_delete=models.RESTRICT,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=4)
    timestamp = models.DateTimeField(auto_now_add=True)
    expiry_timestamp = models.DateTimeField()

    def save(self, *args, **kwargs):
        self.expiry_timestamp = self.timestamp + timedelta(
            seconds=settings.QUOTES_EXPIRY_SECONDS
        )
        return super().save(*args, **kwargs)


class Transaction(models.Model):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    EXPIRED = "EXPIRED"

    TRANSACTION_STATE = [
        (PENDING, "Created"),
        (SUCCESS, "Success"),
        (EXPIRED, "Expired"),
    ]
    quote = models.ForeignKey(Qoute, on_delete=models.RESTRICT)
    state = models.CharField(max_length=255, choices=TRANSACTION_STATE, default=PENDING)
    amount = models.DecimalField(max_digits=10, decimal_places=4)
    timestamp = models.DateTimeField(auto_now_add=True)
    update_timestamp = models.DateTimeField(auto_now=True)
