from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional, Union

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from app.models import Currency, Rate
# from app.tasks import fetch_latest_exchange_rates

"""Currency conversion helpers backed by the stored exchange rates."""


def _quantize(value: Decimal, decimal_places: int) -> Decimal:
    """Round a Decimal to the precision defined for a currency."""
    exponent = Decimal("1").scaleb(-decimal_places) if decimal_places else Decimal("1")
    return value.quantize(exponent, rounding=ROUND_HALF_UP)


def _quantize_rate(value: Decimal) -> Decimal:
    rate_decimal_places = Rate._meta.get_field("rate").decimal_places or 0
    exponent = (
        Decimal("1").scaleb(-rate_decimal_places)
        if rate_decimal_places
        else Decimal("1")
    )
    return value.quantize(exponent, rounding=ROUND_HALF_UP)


def _normalize_rate_payload(raw: Optional[dict]) -> Optional[dict]:
    """Convert cached/db rate payloads into a sanitized dict with Decimal rate and aware timestamp."""
    if not isinstance(raw, dict):
        return None

    rate_value = raw.get("rate")
    timestamp_value = raw.get("timestamp")
    update_timestamp_value = raw.get("update_timestamp")
    if rate_value is None or timestamp_value is None:
        return None
    if update_timestamp_value is None:
        update_timestamp_value = timestamp_value

    try:
        rate_decimal = (
            rate_value if isinstance(rate_value, Decimal) else Decimal(str(rate_value))
        )
    except (InvalidOperation, TypeError, ValueError):
        return None

    if isinstance(timestamp_value, (int, float)):
        timestamp = datetime.fromtimestamp(int(timestamp_value), tz=dt_timezone.utc)
    elif isinstance(timestamp_value, str):
        try:
            timestamp = datetime.fromisoformat(timestamp_value)
        except ValueError:
            return None
    else:
        timestamp = timestamp_value

    if isinstance(timestamp, datetime):
        if timezone.is_naive(timestamp):
            timestamp = timezone.make_aware(timestamp)
    else:
        return None

    if isinstance(update_timestamp_value, (int, float)):
        update_timestamp = datetime.fromtimestamp(int(update_timestamp_value), tz=dt_timezone.utc)
    elif isinstance(update_timestamp_value, str):
        try:
            update_timestamp = datetime.fromisoformat(update_timestamp_value)
        except ValueError:
            return None
    else:
        update_timestamp = update_timestamp_value

    if isinstance(update_timestamp, datetime):
        if timezone.is_naive(update_timestamp):
            update_timestamp = timezone.make_aware(update_timestamp)
    else:
        return None

    return {"rate": rate_decimal, "timestamp": timestamp, "update_timestamp": update_timestamp}


def _ensure_rate_fresh(
    rate_payload: dict, base_currency: Currency, target_currency: Currency
) -> dict:
    """Validate that a rate payload is within the freshness window, raising if stale."""
    cutoff = timezone.now() - timedelta(seconds=settings.EXCHANGE_RATES_EXPIRY_SECONDS)
    if rate_payload["update_timestamp"] < cutoff:
        raise ValueError(
            f"Exchange rate between '{base_currency.currency_code}' and "
            f"'{target_currency.currency_code}' is stale."
        )
    return rate_payload


def _latest_rate(base_currency: Currency, target_currency: Currency):
    """Fetch the most recent rate between two currencies, enforcing freshness."""
    cache_key = f"rate_{base_currency.currency_code}_{target_currency.currency_code}"
    raw_cache = cache.get(cache_key)
    cached_payload = _normalize_rate_payload(raw_cache)
    if cached_payload:
        try:
            return _ensure_rate_fresh(cached_payload, base_currency, target_currency)
        except ValueError:
            cache.delete(cache_key)
            raise
    elif raw_cache is not None:
        cache.delete(cache_key)

    rate = (
        Rate.objects.filter(
            base_currency=base_currency, target_currency=target_currency
        )
        .order_by("-update_timestamp", "-timestamp")
        .first()
    )
    if not rate:
        return None

    payload = {
        "rate": rate.rate,
        "timestamp": rate.timestamp,
        "update_timestamp": rate.update_timestamp,
    }
    payload = _ensure_rate_fresh(payload, base_currency, target_currency)

    cache.set(cache_key, payload, settings.EXCHANGE_RATES_EXPIRY_SECONDS)

    return payload


def convert_currency(
    amount: Union[str, float, int, Decimal],
    from_currency_code: str,
    to_currency_code: str,
    *,
    return_rate: bool = False,
) -> Decimal:
    """Convert an amount between currencies using direct, inverse, or base rates."""
    if not from_currency_code or not to_currency_code:
        raise ValueError("Currency codes must be provided")

    try:
        amount_decimal = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid amount for conversion") from exc

    from_code = str(from_currency_code).upper()
    to_code = str(to_currency_code).upper()

    try:
        from_currency = Currency.objects.get(currency_code=from_code)
    except Currency.DoesNotExist as exc:
        raise ValueError(f"Currency '{from_code}' does not exist") from exc

    try:
        to_currency = Currency.objects.get(currency_code=to_code)
    except Currency.DoesNotExist as exc:
        raise ValueError(f"Currency '{to_code}' does not exist") from exc

    if from_currency == to_currency:
        quantized = _quantize(amount_decimal, to_currency.decimal_places)
        if return_rate:
            return quantized, _quantize_rate(Decimal("1"))
        return quantized

    direct_rate = _latest_rate(from_currency, to_currency)
    if direct_rate:
        converted = amount_decimal * direct_rate["rate"]
        quantized = _quantize(converted, to_currency.decimal_places)
        if return_rate:
            return quantized, _quantize_rate(direct_rate["rate"])
        return quantized

    inverse_rate = _latest_rate(to_currency, from_currency)
    if inverse_rate:
        if inverse_rate["rate"] == 0:
            raise ValueError(
                f"Rate between '{from_code}' and '{to_code}' is zero; cannot convert"
            )
        converted = amount_decimal / inverse_rate["rate"]
        quantized = _quantize(converted, to_currency.decimal_places)
        if return_rate:
            inverse_value = Decimal("1") / inverse_rate["rate"]
            return quantized, _quantize_rate(inverse_value)
        return quantized

    base_code = settings.EXCHANGE_RATES_BASE_CURRENCY.upper()
    if not base_code:
        raise ValueError("Base currency is not configured")

    try:
        base_currency = Currency.objects.get(currency_code=base_code)
    except Currency.DoesNotExist as exc:
        raise ValueError(f"Base currency '{base_code}' does not exist") from exc

    amount_in_base = amount_decimal
    effective_rate = Decimal("1")
    if from_currency != base_currency:
        base_to_from = _latest_rate(base_currency, from_currency)
        if not base_to_from or base_to_from["rate"] == 0:
            raise ValueError(
                f"Missing rate to convert '{from_code}' to base currency '{base_code}'"
            )
        rate_to_base = Decimal("1") / base_to_from["rate"]
        amount_in_base = amount_decimal * rate_to_base
        effective_rate = rate_to_base

    if to_currency == base_currency:
        quantized = _quantize(amount_in_base, to_currency.decimal_places)
        if return_rate:
            return quantized, _quantize_rate(effective_rate)
        return quantized

    base_to_target = _latest_rate(base_currency, to_currency)
    if not base_to_target:
        raise ValueError(
            f"Missing rate to convert base currency '{base_code}' to '{to_code}'"
        )

    converted = amount_in_base * base_to_target["rate"]
    quantized = _quantize(converted, to_currency.decimal_places)
    if return_rate:
        total_rate = effective_rate * base_to_target["rate"]
        return quantized, _quantize_rate(total_rate)
    return quantized
