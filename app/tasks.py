import json
import logging
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

from app.models import Currency, Rate


logger = logging.getLogger(__name__)


def _build_request_url(base_currency: str, target_currency_codes: List[str]) -> str:
    params: Dict[str, str] = {"base": base_currency}

    if target_currency_codes:
        params["symbols"] = ",".join(target_currency_codes)

    api_key = settings.EXCHANGE_RATES_API_KEY
    if api_key:
        params["access_key"] = api_key

    query_string = urlencode(params)
    return (
        f"{settings.EXCHANGE_RATES_API_URL}?{query_string}"
        if query_string
        else settings.EXCHANGE_RATES_API_URL
    )


def _deserialize_timestamp(payload: Dict) -> datetime:
    """Parse provider payload timestamps into aware datetimes, defaulting to now."""
    timestamp_value = payload.get("timestamp")
    if timestamp_value is not None:
        return datetime.fromtimestamp(int(timestamp_value), tz=dt_timezone.utc)

    date_value = payload.get("date")
    if date_value:
        try:
            naive_date = datetime.strptime(date_value, "%Y-%m-%d")
            return timezone.make_aware(
                naive_date, timezone=timezone.get_default_timezone()
            )
        except ValueError:
            logger.warning(
                "Unable to parse date '%s' from exchange rates payload", date_value
            )

    return timezone.now()


def _fetch_payload(url: str) -> Dict:
    request = Request(url)

    with urlopen(request, timeout=settings.EXCHANGE_RATES_API_TIMEOUT) as response:
        if response.status != 200:
            raise HTTPError(
                url, response.status, response.reason, response.headers, None
            )
        payload_bytes = response.read()

    payload = json.loads(payload_bytes.decode("utf-8"))

    if payload.get("error"):
        error_message = (
            payload["error"].get("message")
            if isinstance(payload["error"], dict)
            else payload["error"]
        )
        raise ValueError(f"Exchange rates API error: {error_message}")

    return payload


@shared_task(
    bind=True,
    autoretry_for=(HTTPError, URLError, ValueError, KeyError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def fetch_latest_exchange_rates(self):
    base_currency_code = settings.EXCHANGE_RATES_BASE_CURRENCY.upper()

    try:
        base_currency = Currency.objects.get(
            currency_code=base_currency_code, enabled=True
        )
    except Currency.DoesNotExist:
        logger.warning(
            "Base currency %s is not configured or not enabled; skipping rates fetch",
            base_currency_code,
        )
        return

    target_currency_objects = list(
        Currency.objects.filter(enabled=True).exclude(currency_code=base_currency_code)
    )
    target_currency_map = {
        currency.currency_code: currency for currency in target_currency_objects
    }

    if not target_currency_map:
        logger.info("No enabled target currencies configured; nothing to update")
        return

    request_url = _build_request_url(
        base_currency_code, list(target_currency_map.keys())
    )

    try:
        payload = _fetch_payload(request_url)
    except (HTTPError, URLError, ValueError) as exc:
        logger.error("Failed to fetch exchange rates: %s", exc)
        raise

    fetched_at = _deserialize_timestamp(payload)
    rates = payload.get("rates")

    if not isinstance(rates, dict):
        raise ValueError("Exchange rates payload missing rates map")

    with transaction.atomic():
        for currency_code, rate_value in rates.items():
            if currency_code not in target_currency_map:
                continue

            try:
                rate_decimal = Decimal(str(rate_value))
            except (ValueError, TypeError, InvalidOperation):
                logger.warning(
                    "Skipping rate for %s due to invalid value: %s",
                    currency_code,
                    rate_value,
                )
                continue

            target_currency = target_currency_map[currency_code]

            rate_instance, _ = Rate.objects.update_or_create(
                base_currency=base_currency,
                target_currency=target_currency,
                defaults={
                    "rate": rate_decimal,
                    "timestamp": fetched_at,
                },
            )


            logger.info(
                "Rate updated",
                extra={
                    "event": "rate.updated",
                    "base_currency": base_currency.currency_code,
                    "target_currency": target_currency.currency_code,
                    "rate": str(rate_instance.rate),
                    "timestamp": rate_instance.timestamp.isoformat(),
                },
            )

    logger.info(
        "Exchange rates refreshed for base %s at %s",
        base_currency_code,
        fetched_at.isoformat(),
    )
