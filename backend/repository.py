from decimal import Decimal
from typing import Any, Dict, List, Optional

from .database import get_connection


def _rows(rows: List[Any]) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows]


def _localized(row: Dict[str, Any], lang: str, zh_key: str, en_key: str) -> str:
    """Return only the requested language; public English must not fall back to Chinese."""
    key = en_key if lang.startswith("en") else zh_key
    return str(row.get(key) or "")


def _minor_amount(value: Any) -> str:
    return format(Decimal(int(value or 0)) / Decimal(100), ".2f")


def list_products(lang: str = "zh") -> List[Dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, name, title_name, description, name_en, title_name_en, description_en, base_price, price_usd
            FROM products
            WHERE enabled = 1
            ORDER BY sort_order, name
            """
        ).fetchall()
    result = _rows(rows)
    if lang.startswith("en"):
        for item in result:
            item["name"] = item.get("name_en") or ""
            item["title_name"] = item.get("title_name_en") or ""
            item["description"] = item.get("description_en") or ""
    return result


def get_public_product_snapshot(product_id: str, lang: str = "zh") -> Optional[Dict[str, Any]]:
    """Build the normalized read-only product payload used by the customer configurator."""
    language = "en" if lang.startswith("en") else "zh"
    with get_connection() as connection:
        product_row = connection.execute(
            """
            SELECT id, name, name_en, title_name, title_name_en,
                   description, description_en, translation_status
            FROM products
            WHERE id = ? AND enabled = 1
            """,
            (product_id,),
        ).fetchone()
        if product_row is None:
            return None

        color_rows = connection.execute(
            """
            SELECT code, label, label_en, display_color, image_path,
                   image_width, image_height, is_default, translation_status
            FROM product_colors
            WHERE product_id = ? AND enabled = 1
            ORDER BY sort_order, code
            """,
            (product_id,),
        ).fetchall()
        group_rows = connection.execute(
            """
            SELECT id, option_type, required, single_select, sort_order
            FROM product_base_option_groups
            WHERE product_id = ? AND enabled = 1
            ORDER BY sort_order, id
            """,
            (product_id,),
        ).fetchall()
        base_option_rows = connection.execute(
            """
            SELECT o.id, o.group_id, g.option_type, o.name_zh, o.name_en,
                   o.price_cny_minor, o.price_usd_minor, o.price_confirmed,
                   o.is_free, o.sort_order, o.translation_status
            FROM product_base_options o
            JOIN product_base_option_groups g ON g.id = o.group_id
            WHERE g.product_id = ? AND g.enabled = 1 AND o.enabled = 1
            ORDER BY g.sort_order, o.sort_order, o.id
            """,
            (product_id,),
        ).fetchall()
        variant_rows = connection.execute(
            """
            SELECT id, motor_option_id, channel_option_id,
                   price_cny_minor, price_usd_minor, price_confirmed
            FROM product_price_variants
            WHERE product_id = ? AND enabled = 1
            ORDER BY id
            """,
            (product_id,),
        ).fetchall()
        optional_rows = connection.execute(
            """
            SELECT c.id AS category_id, c.name AS category_name_zh,
                   c.name_en AS category_name_en,
                   c.description AS category_description_zh,
                   c.description_en AS category_description_en,
                   c.sort_order AS category_sort, c.translation_status AS category_translation_status,
                   o.id, o.code, o.name AS name_zh, o.name_en,
                   o.description AS description_zh, o.description_en,
                   o.notes AS note_zh, o.note_en,
                   COALESCE(po.image_override, o.image_path) AS image_path,
                   o.image_width, o.image_height,
                   COALESCE(po.price_override, o.price) AS price_cny,
                   o.price_usd, o.translation_status,
                   po.mapping_id, po.description_override, po.description_override_en,
                   po.sort_order AS mapping_sort, o.sort_order AS option_sort
            FROM product_options po
            JOIN options o ON o.id = po.option_id
            JOIN categories c ON c.id = o.category_id
            WHERE po.product_id = ? AND po.enabled = 1
              AND o.enabled = 1 AND o.deleted_at IS NULL
              AND c.enabled = 1 AND c.catalog_type = 'optional'
            ORDER BY c.sort_order, o.sort_order, o.id
            """,
            (product_id,),
        ).fetchall()
        specification_rows = connection.execute(
            """
            SELECT id, label, label_en, value, value_en, sort_order
            FROM product_specifications
            WHERE product_id = ?
            ORDER BY sort_order, id
            """,
            (product_id,),
        ).fetchall()

    product = dict(product_row)
    colors = []
    for source in color_rows:
        row = dict(source)
        colors.append(
            {
                "id": row["code"],
                "code": row["code"],
                "name": _localized(row, language, "label", "label_en"),
                "display_color": row.get("display_color") or "#374151",
                "image": {
                    "path": row.get("image_path"),
                    "width": row.get("image_width"),
                    "height": row.get("image_height"),
                },
                "is_default": bool(row.get("is_default")),
                "translation_status": row.get("translation_status") or "missing",
            }
        )

    base_options_by_group: Dict[str, List[Dict[str, Any]]] = {}
    for source in base_option_rows:
        row = dict(source)
        base_options_by_group.setdefault(row["group_id"], []).append(
            {
                "id": row["id"],
                "name": _localized(row, language, "name_zh", "name_en"),
                "price_cny": _minor_amount(row.get("price_cny_minor")),
                "price_usd": _minor_amount(row.get("price_usd_minor")),
                "price_confirmed": bool(row.get("price_confirmed")),
                "is_free": bool(row.get("is_free")),
                "translation_status": row.get("translation_status") or "missing",
            }
        )
    group_labels = {
        "zh": {"motor": "电机配置", "power": "电源配置", "channel": "通道配置"},
        "en": {"motor": "Motor", "power": "Power Supply", "channel": "Channels"},
    }
    base_groups = [
        {
            "id": row["id"],
            "type": row["option_type"],
            "name": group_labels[language][row["option_type"]],
            "required": bool(row["required"]),
            "single_select": True,
            "options": base_options_by_group.get(row["id"], []),
        }
        for row in map(dict, group_rows)
    ]

    optional_categories: Dict[str, Dict[str, Any]] = {}
    for source in optional_rows:
        row = dict(source)
        category = optional_categories.setdefault(
            row["category_id"],
            {
                "id": row["category_id"],
                "name": _localized(row, language, "category_name_zh", "category_name_en"),
                "description": _localized(
                    row, language, "category_description_zh", "category_description_en"
                ),
                "multiple": True,
                "translation_status": row.get("category_translation_status") or "missing",
                "options": [],
            },
        )
        category["options"].append(
            {
                "id": row["id"],
                "code": row.get("code") or "",
                "name": _localized(row, language, "name_zh", "name_en"),
                "description": _localized(row, language, "description_zh", "description_en"),
                "note": _localized(row, language, "note_zh", "note_en"),
                "special_note": _localized(
                    row, language, "description_override", "description_override_en"
                ),
                "image": {
                    "path": row.get("image_path"),
                    "width": row.get("image_width"),
                    "height": row.get("image_height"),
                },
                "price_cny": str(row.get("price_cny") or 0),
                "price_usd": str(row.get("price_usd") or 0),
                "price_confirmed": bool(row.get("price_cny") or row.get("price_usd")),
                "mapping_id": row.get("mapping_id"),
                "translation_status": row.get("translation_status") or "missing",
            }
        )

    variants = [
        {
            "id": row["id"],
            "motor_option_id": row["motor_option_id"],
            "channel_option_id": row["channel_option_id"],
            "price_cny": _minor_amount(row["price_cny_minor"]),
            "price_usd": _minor_amount(row["price_usd_minor"]),
            "price_confirmed": bool(row["price_confirmed"]),
        }
        for row in map(dict, variant_rows)
    ]
    specifications = [
        {
            "id": row["id"],
            "label": _localized(dict(row), language, "label", "label_en"),
            "value": _localized(dict(row), language, "value", "value_en"),
        }
        for row in specification_rows
    ]
    return {
        "schema_version": 2,
        "language": language,
        "id": product["id"],
        "model": _localized(product, language, "name", "name_en"),
        "name": _localized(product, language, "title_name", "title_name_en"),
        "overview": _localized(product, language, "description", "description_en"),
        "translation_status": product.get("translation_status") or "missing",
        "colors": colors,
        "base_option_groups": base_groups,
        "price_variants": variants,
        "optional_categories": list(optional_categories.values()),
        "specifications": specifications,
    }


def get_product(product_id: str, lang: str = "zh") -> Optional[Dict[str, Any]]:
    with get_connection() as connection:
        product_row = connection.execute(
            """
            SELECT id, name, title_name, description, name_en, title_name_en, description_en, base_price, price_usd
            FROM products
            WHERE id = ? AND enabled = 1
            """,
            (product_id,),
        ).fetchone()
        if product_row is None:
            return None

        color_rows = connection.execute(
            """
            SELECT code, label, label_en, image_path, is_default
            FROM product_colors
            WHERE product_id = ?
            ORDER BY sort_order, code
            """,
            (product_id,),
        ).fetchall()
        option_rows = connection.execute(
            """
            SELECT
                c.id AS category_id,
                c.name AS category_name,
                c.description AS category_description, c.name_en AS category_name_en, c.description_en AS category_description_en,
                c.multiple,
                o.id AS option_id,
                o.code,
                o.name, o.name_en, o.description, o.description_en,
                po.description_override, po.description_override_en,
                COALESCE(po.image_override, o.image_path) AS image_path,
                COALESCE(po.price_override, o.price) AS price,
                po.mapping_id,
                mp.base_price_cny AS motor_base_price_cny,
                mp.base_price_usd AS motor_base_price_usd
            FROM product_options po
            JOIN options o ON o.id = po.option_id
            JOIN categories c ON c.id = o.category_id
            LEFT JOIN product_motor_prices mp ON mp.product_id = po.product_id AND mp.motor_option_id = po.option_id
            WHERE po.product_id = ? AND po.enabled = 1 AND o.enabled = 1
            ORDER BY c.sort_order, po.sort_order, o.sort_order, o.name
            """,
            (product_id,),
        ).fetchall()
        specification_rows = connection.execute(
            "SELECT id, label, label_en, value, value_en, sort_order FROM product_specifications WHERE product_id = ? ORDER BY sort_order, id",
            (product_id,),
        ).fetchall()

    product = dict(product_row)
    if lang.startswith("en"):
        product["name"] = product.get("name_en") or product["name"]; product["title_name"] = product.get("title_name_en") or product["title_name"]; product["description"] = product.get("description_en") or product["description"]
    product["colors"] = _rows(color_rows)
    if lang.startswith("en"):
        for color in product["colors"]:
            color["label"] = color.get("label_en") or color["label"]
    categories: Dict[str, Dict[str, Any]] = {}
    for row in option_rows:
        item = dict(row)
        category_id = item.pop("category_id")
        category_multiple = bool(item.pop("multiple"))
        category = categories.setdefault(
            category_id,
            {
                "id": category_id,
                "name": (
                    item.pop("category_name_en") or item["category_name"]
                    if lang.startswith("en")
                    else item["category_name"]
                ),
                "description": (
                    item.pop("category_description_en") or item["category_description"]
                    if lang.startswith("en")
                    else item["category_description"]
                ),
                "multiple": (
                    False
                    if category_id in ("motor", "voltage")
                    else category_multiple
                ),
                "options": [],
            },
        )
        item.pop("category_name", None)
        item.pop("category_name_en", None)
        item.pop("category_description", None)
        item.pop("category_description_en", None)
        item["id"] = item.pop("option_id")
        if lang.startswith("en"):
            item["name"] = item.get("name_en") or item["name"]
            item["description"] = item.get("description_en") or item["description"]
            item["special_note"] = item.get("description_override_en") or ""
        else:
            item["special_note"] = item.get("description_override") or ""
        item.pop("description_override", None)
        item.pop("description_override_en", None)
        category["options"].append(item)
    product["categories"] = list(categories.values())
    product["specifications"] = []
    for row in specification_rows:
        spec = dict(row)
        if lang.startswith("en"):
            spec["label"] = spec.get("label_en") or spec["label"]
            spec["value"] = spec.get("value_en") or spec["value"]
        product["specifications"].append(spec)
    return product
