from typing import Any, Dict, List, Optional

from .database import get_connection


def _rows(rows: List[Any]) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows]


def list_products(lang: str = "zh") -> List[Dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, name, title_name, description, name_en, title_name_en, description_en, base_price
            FROM products
            WHERE enabled = 1
            ORDER BY sort_order, name
            """
        ).fetchall()
    result = _rows(rows)
    if lang.startswith("en"):
        for item in result:
            item["name"] = item.get("name_en") or item["name"]; item["title_name"] = item.get("title_name_en") or item["title_name"]; item["description"] = item.get("description_en") or item["description"]
    return result


def get_product(product_id: str, lang: str = "zh") -> Optional[Dict[str, Any]]:
    with get_connection() as connection:
        product_row = connection.execute(
            """
            SELECT id, name, title_name, description, name_en, title_name_en, description_en, base_price
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
                po.mapping_id
            FROM product_options po
            JOIN options o ON o.id = po.option_id
            JOIN categories c ON c.id = o.category_id
            WHERE po.product_id = ? AND po.enabled = 1 AND o.enabled = 1
            ORDER BY c.sort_order, po.sort_order, o.sort_order, o.name
            """,
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
    return product
