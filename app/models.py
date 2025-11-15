from datetime import timedelta
from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


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
    update_timestamp = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-update_timestamp", "-timestamp"]


@receiver(post_save, sender=Rate)
def update_rate_cache(sender, instance: Rate, **_kwargs):
    cache_key = f"rate_{instance.base_currency.currency_code}_{instance.target_currency.currency_code}"
    cache_payload = {
        "rate": instance.rate,
        "timestamp": instance.timestamp,
        "update_timestamp": instance.update_timestamp,
    }
    cache.set(cache_key, cache_payload, settings.EXCHANGE_RATES_EXPIRY_SECONDS)


class Quote(models.Model):
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
    converted_amount = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True
    )
    amount = models.DecimalField(max_digits=10, decimal_places=4)
    rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    expiry_timestamp = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.timestamp:
            self.timestamp = timezone.now()

        self.expiry_timestamp = self.timestamp + timedelta(
            seconds=settings.QUOTES_EXPIRY_SECONDS
        )
        return super().save(*args, **kwargs)


class Transaction(models.Model):
    quote = models.ForeignKey(Quote, on_delete=models.RESTRICT)
    amount = models.DecimalField(max_digits=10, decimal_places=4)
    timestamp = models.DateTimeField(auto_now_add=True)
    update_timestamp = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["quote", "amount"],
                name="unique_transaction_quote_amount",
            )
        ]
