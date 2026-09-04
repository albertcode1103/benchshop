"""Server-side pricing for device configurations and catalog references."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional

from .database import get_connection
from .catalog_refactor_repository import CatalogValidationError


def _minor_to_decimal_string(value: int) -> str:
    return format(Decimal(int(value or 0)) / Decimal(100), ".2f")


def _major_to_minor(value: Any) -> int:
    try:
        amount = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise CatalogValidationError("CATALOG_PRICE_INVALID", "price")
    if amount < 0:
        raise CatalogValidationError("CATALOG_PRICE_INVALID", "price")
    return int(amount * 100)


def _localized(row: Dict[str, Any], language: str, zh_key: str, en_key: str) -> str:
    if language == "en":
        return str(row.get(en_key) or "")
    return str(row.get(zh_key) or "")


def calculate_product_price(
    product_id: str,
    *,
    motor_option_id: Optional[str],
    channel_option_id: Optional[str],
    power_option_id: Optional[str],
    optional_config_ids: Iterable[str],
    currency: str,
    language: str = "zh",
) -> Dict[str, Any]:
    selected_currency = currency.upper()
    if selected_currency not in ("CNY", "USD"):
        raise CatalogValidationError("CATALOG_CURRENCY_INVALID", "currency")
    selected_language = "en" if language == "en" else "zh"
    optional_ids = list(dict.fromkeys(str(item) for item in optional_config_ids))

    with get_connection() as db:
        product_row = db.execute(
            """
            SELECT id, name, name_en, title_name, title_name_en, enabled
            FROM products WHERE id = ?
            """,
            (product_id,),
        ).fetchone()
        if product_row is None:
            raise CatalogValidationError("CATALOG_PRODUCT_NOT_FOUND", "product_id")
        product = dict(product_row)

        # Prefer an exact combination, then fall back to a variant whose other
        # selected dimension is intentionally not part of this model's price.
        # For example, CR318Pro keeps a motor selection for the specification
        # but its base price is determined only by the selected channel count.
        variant_row = None
        variant_candidates = [
            (motor_option_id, channel_option_id),
            (None, channel_option_id),
            (motor_option_id, None),
        ]
        for candidate_motor_id, candidate_channel_id in dict.fromkeys(variant_candidates):
            if candidate_motor_id is None and candidate_channel_id is None:
                continue
            variant_row = db.execute(
                """
                SELECT id, price_cny_minor, price_usd_minor, price_confirmed
                FROM product_price_variants
                WHERE product_id = ? AND enabled = 1
                  AND ((motor_option_id = ?) OR (motor_option_id IS NULL AND ? IS NULL))
                  AND ((channel_option_id = ?) OR (channel_option_id IS NULL AND ? IS NULL))
                LIMIT 1
                """,
                (
                    product_id,
                    candidate_motor_id,
                    candidate_motor_id,
                    candidate_channel_id,
                    candidate_channel_id,
                ),
            ).fetchone()
            if variant_row is not None:
                break
        if variant_row is None:
            raise CatalogValidationError("PRICE_VARIANT_NOT_FOUND", "base_options")
        variant = dict(variant_row)
        price_column = "price_usd_minor" if selected_currency == "USD" else "price_cny_minor"
        base_minor = int(variant[price_column] or 0)

        selected_labels: Dict[str, str] = {}
        for option_type, option_id in (
            ("motor", motor_option_id),
            ("channel", channel_option_id),
        ):
            if not option_id:
                continue
            row = db.execute(
                """
                SELECT o.name_zh, o.name_en
                FROM product_base_options o
                JOIN product_base_option_groups g ON g.id = o.group_id
                WHERE o.id = ? AND g.product_id = ? AND g.option_type = ?
                  AND o.enabled = 1 AND g.enabled = 1
                """,
                (option_id, product_id, option_type),
            ).fetchone()
            if row is None:
                raise CatalogValidationError(
                    "BASE_OPTION_NOT_AVAILABLE",
                    "{}_option_id".format(option_type),
                )
            selected_labels[option_type] = _localized(dict(row), selected_language, "name_zh", "name_en")

        power_minor = 0
        power_line = None
        if power_option_id:
            power_row = db.execute(
                """
                SELECT o.name_zh, o.name_en, o.price_cny_minor,
                       o.price_usd_minor, o.price_confirmed, o.is_free
                FROM product_base_options o
                JOIN product_base_option_groups g ON g.id = o.group_id
                WHERE o.id = ? AND g.product_id = ? AND g.option_type = 'power'
                  AND o.enabled = 1 AND g.enabled = 1
                """,
                (power_option_id, product_id),
            ).fetchone()
            if power_row is None:
                raise CatalogValidationError("BASE_OPTION_NOT_AVAILABLE", "power_option_id")
            power = dict(power_row)
            power_minor = int(power[price_column] or 0)
            selected_labels["power"] = _localized(power, selected_language, "name_zh", "name_en")
            power_line = {
                "kind": "surcharge",
                "source_id": power_option_id,
                "label": selected_labels["power"],
                "amount": _minor_to_decimal_string(power_minor),
                "price_confirmed": bool(power["price_confirmed"]),
                "is_free": bool(power["is_free"]),
            }

        optional_lines: List[Dict[str, Any]] = []
        optional_minor = 0
        if optional_ids:
            placeholders = ",".join("?" for _ in optional_ids)
            rows = db.execute(
                """
                SELECT o.id, o.code, o.name, o.name_en, o.price, o.price_usd,
                       po.price_override
                FROM options o
                JOIN categories c ON c.id = o.category_id
                JOIN product_options po
                  ON po.option_id = o.id AND po.product_id = ? AND po.enabled = 1
                WHERE o.id IN ({})
                  AND o.enabled = 1 AND o.deleted_at IS NULL
                  AND c.enabled = 1 AND c.catalog_type = 'optional'
                """.format(placeholders),
                [product_id] + optional_ids,
            ).fetchall()
            by_id = {row["id"]: dict(row) for row in rows}
            missing = [option_id for option_id in optional_ids if option_id not in by_id]
            if missing:
                raise CatalogValidationError(
                    "CATALOG_OPTION_NOT_AVAILABLE",
                    "optional_config_ids",
                    {"option_ids": missing},
                )
            for option_id in optional_ids:
                row = by_id[option_id]
                if selected_currency == "USD":
                    whole_amount = row["price_usd"]
                else:
                    whole_amount = row["price_override"] if row["price_override"] is not None else row["price"]
                minor = _major_to_minor(whole_amount)
                optional_minor += minor
                optional_lines.append(
                    {
                        "kind": "optional",
                        "source_id": option_id,
                        "code": row["code"],
                        "label": _localized(row, selected_language, "name", "name_en"),
                        "amount": _minor_to_decimal_string(minor),
                        "price_confirmed": minor > 0,
                        "is_free": False,
                    }
                )

    lines = [
        {
            "kind": "base_price",
            "source_id": variant["id"],
            "label": " / ".join(
                label for key, label in selected_labels.items()
                if key in ("motor", "channel") and label
            ),
            "amount": _minor_to_decimal_string(base_minor),
            "price_confirmed": bool(variant["price_confirmed"]),
            "is_free": False,
        }
    ]
    if power_line:
        lines.append(power_line)
    lines.extend(optional_lines)
    total_minor = base_minor + power_minor + optional_minor
    return {
        "product_id": product_id,
        "product_model": product["name_en"] if selected_language == "en" else product["name"],
        "product_name": product["title_name_en"] if selected_language == "en" else product["title_name"],
        "currency": selected_currency,
        "base_price": _minor_to_decimal_string(base_minor),
        "surcharge_total": _minor_to_decimal_string(power_minor),
        "optional_total": _minor_to_decimal_string(optional_minor),
        "grand_total": _minor_to_decimal_string(total_minor),
        "price_confirmed": all(bool(line["price_confirmed"]) or bool(line["is_free"]) for line in lines),
        "selected": selected_labels,
        "lines": lines,
    }


def list_catalog_reference_prices(catalog_type: str, language: str = "zh") -> List[Dict[str, Any]]:
    if catalog_type not in ("optional", "tools", "accessories"):
        raise CatalogValidationError("CATALOG_TYPE_INVALID", "catalog_type")
    selected_language = "en" if language == "en" else "zh"
    with get_connection() as db:
        rows = db.execute(
            """
            SELECT o.id, o.code, o.name, o.name_en, o.price, o.price_usd,
                   o.translation_status
            FROM options o
            JOIN categories c ON c.id = o.category_id
            WHERE c.catalog_type = ? AND c.enabled = 1
              AND o.enabled = 1 AND o.deleted_at IS NULL
            ORDER BY c.sort_order, o.sort_order, o.id
            """,
            (catalog_type,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "code": row["code"],
            "name": row["name_en"] if selected_language == "en" else row["name"],
            "price_cny": _minor_to_decimal_string(_major_to_minor(row["price"])),
            "price_usd": _minor_to_decimal_string(_major_to_minor(row["price_usd"])),
            "translation_status": row["translation_status"],
        }
        for row in rows
    ]
