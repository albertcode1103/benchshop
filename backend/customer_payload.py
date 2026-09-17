"""Customer-facing payload sanitizers.

Prices and internal catalog notes remain in stored snapshots for staff use,
but must not be serialized by customer catalog/cart/share endpoints.
"""

from copy import deepcopy
from typing import Any


PRICE_KEYS = {
    "amount",
    "base_price",
    "grand_total",
    "is_free",
    "line_total",
    "motor_base_price_cny",
    "motor_base_price_usd",
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


CATALOG_NOTE_KEYS = {
    "note", "notes", "note_zh", "note_en", "special_note", "specialNote",
    "description_override", "description_override_en",
}


def without_prices(value: Any, *, _catalog: bool = False) -> Any:
    """Remove prices and catalog notes; preserve customer-authored share notes."""
    if isinstance(value, dict):
        # Keep customer-authored share notes, but remove internal catalog notes
        # from both current records and historical cart/share/inquiry snapshots.
        catalog = (
            _catalog or "option_id" in value
            or ("category_id" in value and "code" in value)
            or value.get("catalog_type") in ("optional", "tools", "accessories")
            or value.get("item_type") in ("tool", "accessory")
        )
        return {
            key: without_prices(item, _catalog=catalog or key == "options")
            for key, item in value.items()
            if key not in PRICE_KEYS and not (catalog and key in CATALOG_NOTE_KEYS)
        }
    if isinstance(value, list):
        return [without_prices(item, _catalog=_catalog) for item in value]
    if isinstance(value, tuple):
        return tuple(without_prices(item, _catalog=_catalog) for item in value)
    return deepcopy(value)
