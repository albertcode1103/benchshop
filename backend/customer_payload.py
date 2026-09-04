"""Customer-facing payload sanitizers.

Prices remain in the database and immutable commerce snapshots for staff
quoting, but must never be serialized by customer-facing endpoints.
"""

from copy import deepcopy
from typing import Any


PRICE_KEYS = {
    "amount",
    "base_price",
    "grand_total",
    "is_free",
    "line_total",
    "price",
    "price_cny",
    "price_cny_minor",
    "price_usd",
    "price_usd_minor",
    "price_confirmed",
    "pricing",
    "pricing_by_currency",
    "reference_price",
    "total_price",
    "unit_price",
}


def without_prices(value: Any) -> Any:
    """Return a deep customer-safe copy without price-bearing fields."""
    if isinstance(value, dict):
        return {
            key: without_prices(item)
            for key, item in value.items()
            if key not in PRICE_KEYS
        }
    if isinstance(value, list):
        return [without_prices(item) for item in value]
    if isinstance(value, tuple):
        return tuple(without_prices(item) for item in value)
    return deepcopy(value)
