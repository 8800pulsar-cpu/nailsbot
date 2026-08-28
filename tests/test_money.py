from decimal import Decimal

from app.utils.format import format_price, parse_price


def test_price_uses_decimal_not_float():
    price = parse_price("1500")
    assert price == Decimal("1500.00")
    assert format_price(price) == "1500 ₽"
    assert format_price(Decimal("1500.50")) == "1500.50 ₽"
