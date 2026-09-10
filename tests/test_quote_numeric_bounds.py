import pytest
from backend.quote_repository import _normalize_quote_items
from backend.quote_repository import save_quote
from unittest.mock import patch


@pytest.mark.parametrize("quantity", ["Infinity", "-Infinity", "1e10000", "NaN"])
def test_nonfinite_quantity_is_validation_error(quantity):
    with pytest.raises(ValueError):
        _normalize_quote_items([{"kind": "product", "name": "Device", "quantity": quantity, "price": 1}])


def test_valid_quantity_and_price_unchanged():
    row = _normalize_quote_items([{"kind": "product", "name": "Device", "quantity": 2, "price": 12.34}])[0]
    assert row["quantity"] == 2
    assert row["price"] == 12.34


@pytest.mark.parametrize("field", ["category_sort_order", "catalog_category_sort_order",
                                   "sort_order", "catalog_sort_order"])
@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_nonfinite_catalog_order_does_not_crash_legacy_reads(field, value):
    rows = _normalize_quote_items([
        {"kind": "tool", "code": "B", "quantity": 1, "price": 2, field: value},
        {"kind": "tool", "code": "A", "quantity": 1, "price": 3, field: 1},
    ])
    assert [row["code"] for row in rows] == ["A", "B"]


def test_oversized_legacy_reference_price_uses_safe_fallback():
    row = _normalize_quote_items([
        {"kind": "tool", "quantity": 1, "price": 2, "reference_price": 10 ** 400}
    ])[0]
    assert row["reference_price"] == 0
    assert row["price"] == 2


def test_computed_total_overflow_is_rejected_before_database_write():
    with patch("backend.quote_repository.get_connection") as connection:
        with pytest.raises(ValueError, match="总额"):
            save_quote(None, "test", "Overflow", [
                {"kind": "product", "quantity": 10, "price": 1e308}], 0)
        connection.assert_not_called()
