from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Union

from django.conf import settings

from app.models import Currency, Rate

"""Currency conversion helpers backed by the stored exchange rates."""


def _quantize(value: Decimal, decimal_places: int) -> Decimal:
    """Round a Decimal to the precision defined for a currency."""
    exponent = Decimal("1").scaleb(-decimal_places) if decimal_places else Decimal("1")
    return value.quantize(exponent, rounding=ROUND_HALF_UP)


def _latest_rate(base_currency: Currency, target_currency: Currency):
    """Fetch the most recent rate between two currencies, if available."""
    return (
        Rate.objects.filter(base_currency=base_currency, target_currency=target_currency)
        .order_by("-timestamp")
        .first()
    )


def convert_currency(
    amount: Union[str, float, int, Decimal],
    from_currency_code: str,
    to_currency_code: str,
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
        return _quantize(amount_decimal, to_currency.decimal_places)

    direct_rate = _latest_rate(from_currency, to_currency)
    if direct_rate:
        converted = amount_decimal * direct_rate.rate
        return _quantize(converted, to_currency.decimal_places)

    inverse_rate = _latest_rate(to_currency, from_currency)
    if inverse_rate:
        if inverse_rate.rate == 0:
            raise ValueError(
                f"Rate between '{from_code}' and '{to_code}' is zero; cannot convert"
            )
        converted = amount_decimal / inverse_rate.rate
        return _quantize(converted, to_currency.decimal_places)

    base_code = settings.EXCHANGE_RATES_BASE_CURRENCY.upper()
    if not base_code:
        raise ValueError("Base currency is not configured")

    try:
        base_currency = Currency.objects.get(currency_code=base_code)
    except Currency.DoesNotExist as exc:
        raise ValueError(f"Base currency '{base_code}' does not exist") from exc

    amount_in_base = amount_decimal
    if from_currency != base_currency:
        base_to_from = _latest_rate(base_currency, from_currency)
        if not base_to_from or base_to_from.rate == 0:
            raise ValueError(
                f"Missing rate to convert '{from_code}' to base currency '{base_code}'"
            )
        amount_in_base = amount_decimal / base_to_from.rate

    if to_currency == base_currency:
        return _quantize(amount_in_base, to_currency.decimal_places)

    base_to_target = _latest_rate(base_currency, to_currency)
    if not base_to_target:
        raise ValueError(
            f"Missing rate to convert base currency '{base_code}' to '{to_code}'"
        )

    converted = amount_in_base * base_to_target.rate
    return _quantize(converted, to_currency.decimal_places)
