from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Union

from django.conf import settings
from django.core.cache import cache

from app.models import Currency, Rate

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


def _latest_rate(base_currency: Currency, target_currency: Currency):
    """Fetch the most recent rate between two currencies, if available."""
    # Check cache first.
    cache_key = f"rate_{base_currency.currency_code}_{target_currency.currency_code}"
    payload = cache.get(cache_key)
    if payload:
        return payload

    rate = (
        Rate.objects.filter(
            base_currency=base_currency, target_currency=target_currency
        )
        .order_by("-timestamp")
        .first()
    )
    if not rate:
        return None
    payload = {"rate": rate.rate, "timestamp": rate.timestamp}

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
