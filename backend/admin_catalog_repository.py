from typing import Any, Dict, List, Optional

from .database import get_connection
import uuid

def create_product(values: Dict[str, Any]) -> Dict[str, Any]:
    product_id = values["id"].strip().lower()
    with get_connection() as db:
        db.execute("INSERT INTO products(id,name,name_en,title_name,title_name_en,description,description_en,base_price,price_usd,enabled,sort_order) VALUES(?,?,?,?,?,?,?,?,?,1,999)", (product_id, values["name"], values.get("name_en", ""), values.get("title_name", values["name"]), values.get("title_name_en", ""), values.get("description", ""), values.get("description_en", ""), int(values.get("base_price", 0)), int(values.get("price_usd", 0))))
        db.execute("INSERT INTO product_colors(product_id,code,label,is_default,sort_order) VALUES(?,?,?,?,0)", (product_id, "Green", "Green", 1))
    return get_admin_product(product_id)


def list_config_categories() -> List[Dict[str, Any]]:
    with get_connection() as connection:
        categories = connection.execute("SELECT id, name, name_en, description, description_en, multiple, sort_order FROM categories ORDER BY sort_order, name").fetchall()
        result = []
        for category in categories:
            item = dict(category); item["multiple"] = bool(item["multiple"])
            item["options"] = [dict(row) for row in connection.execute("SELECT id, code, name, name_en, image_path, description, description_en, notes, price, price_usd, enabled, sort_order FROM options WHERE category_id = ? ORDER BY sort_order, name", (item["id"],)).fetchall()]
            for option in item["options"]: option["enabled"] = bool(option["enabled"])
            result.append(item)
    return result


def update_config_option(option_id: str, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed = ("code", "name", "name_en", "image_path", "description", "description_en", "notes", "price", "price_usd", "enabled", "sort_order")
    updates = {key: values[key] for key in allowed if key in values}
    if not updates: return None
    assignments = ", ".join("{} = ?".format(key) for key in updates)
    params = [int(v) if key == "enabled" else v for key, v in updates.items()]; params.append(option_id)
    with get_connection() as connection:
        row = connection.execute("UPDATE options SET {} WHERE id = ?".format(assignments), params)
        if row.rowcount == 0: return None
        result = connection.execute("SELECT id, category_id, code, name, name_en, image_path, description, description_en, notes, price, price_usd, enabled, sort_order FROM options WHERE id = ?", (option_id,)).fetchone()
    item = dict(result); item["enabled"] = bool(item["enabled"]); return item


def create_config_category(name: str, description: str = "", multiple: bool = True, name_en: str = "", description_en: str = "") -> Dict[str, Any]:
    category_id = uuid.uuid4().hex[:12]
    with get_connection() as connection:
        sort_order = connection.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM categories").fetchone()[0]
        connection.execute("INSERT INTO categories (id, name, name_en, description, description_en, multiple, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?)", (category_id, name.strip(), name_en.strip(), description.strip(), description_en.strip(), int(multiple), sort_order))
    return {"id": category_id, "name": name.strip(), "name_en": name_en.strip(), "description": description.strip(), "description_en": description_en.strip(), "multiple": bool(multiple), "options": []}


def create_config_option(category_id: str, code: str, name: str, **values: Any) -> Dict[str, Any]:
    option_id = "opt-" + uuid.uuid4().hex[:16]
    with get_connection() as connection:
        sort_order = connection.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM options WHERE category_id = ?", (category_id,)).fetchone()[0]
        connection.execute("INSERT INTO options (id, category_id, code, name, name_en, image_path, description, description_en, notes, price, price_usd, enabled, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (option_id, category_id, code.strip(), name.strip(), values.get("name_en") or "", values.get("image_path"), values.get("description") or "", values.get("description_en") or "", values.get("notes") or "", values.get("price") or 0, values.get("price_usd") or 0, int(values.get("enabled", True)), sort_order))
        result = connection.execute("SELECT id, category_id, code, name, name_en, image_path, description, description_en, notes, price, price_usd, enabled, sort_order FROM options WHERE id = ?", (option_id,)).fetchone()
    item = dict(result); item["enabled"] = bool(item["enabled"]); return item

def update_config_category(category_id: str, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    updates = {k: values[k] for k in ("name", "name_en", "description", "description_en", "multiple", "sort_order") if k in values}
    if not updates: return None
    assignments = ", ".join(f"{k} = ?" for k in updates)
    params = [int(v) if k == "multiple" else v for k, v in updates.items()] + [category_id]
    with get_connection() as connection:
        cur = connection.execute(f"UPDATE categories SET {assignments} WHERE id = ?", params)
    if cur.rowcount == 0: return None
    return next((x for x in list_config_categories() if x["id"] == category_id), None)


def list_admin_products() -> List[Dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, name, name_en, title_name, title_name_en, description, description_en, base_price, price_usd, enabled, sort_order,
                   created_at, updated_at
            FROM products
            ORDER BY sort_order, name
            """
        ).fetchall()
    items = [dict(row) for row in rows]
    for item in items:
        item["enabled"] = bool(item["enabled"])
    return items


def get_admin_product(product_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as connection:
        product_row = connection.execute(
            """
            SELECT id, name, name_en, title_name, title_name_en,
                   description, description_en, base_price, price_usd,
                   enabled, sort_order,
                   created_at, updated_at
            FROM products WHERE id = ?
            """,
            (product_id,),
        ).fetchone()
        if product_row is None:
            return None

        color_rows = connection.execute(
            """
            SELECT code, label, image_path, is_default, sort_order
            FROM product_colors WHERE product_id = ? ORDER BY sort_order, code
            """,
            (product_id,),
        ).fetchall()
        option_rows = connection.execute(
            """
            SELECT o.id, o.category_id, o.code, o.name, o.name_en,
                   o.description, o.description_en, o.image_path,
                   o.price, o.price_usd, o.enabled, o.sort_order,
                   CASE WHEN po.option_id IS NULL THEN 0 ELSE 1 END AS selected,
                   po.description_override, po.description_override_en, po.image_override, po.price_override
            FROM options o
            LEFT JOIN product_options po
              ON po.option_id = o.id AND po.product_id = ? AND po.enabled = 1
            ORDER BY o.category_id, o.sort_order, o.name
            """,
            (product_id,),
        ).fetchall()
        category_rows = connection.execute(
            "SELECT id, name, name_en, description, description_en, multiple, sort_order FROM categories ORDER BY sort_order, name"
        ).fetchall()

    product = dict(product_row)
    product["enabled"] = bool(product["enabled"])
    product["colors"] = []
    for row in color_rows:
        color = dict(row)
        color["is_default"] = bool(color["is_default"])
        product["colors"].append(color)

    options_by_category: Dict[str, List[Dict[str, Any]]] = {}
    for row in option_rows:
        option = dict(row)
        option["enabled"] = bool(option["enabled"])
        option["selected"] = bool(option["selected"])
        options_by_category.setdefault(option.pop("category_id"), []).append(option)

    product["categories"] = []
    for row in category_rows:
        category = dict(row)
        category["multiple"] = bool(category["multiple"])
        category["options"] = options_by_category.get(category["id"], [])
        product["categories"].append(category)
    return product


def update_product(product_id: str, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed = ("name", "title_name", "name_en", "title_name_en", "description", "description_en", "base_price", "price_usd", "enabled", "sort_order")
    updates = {key: values[key] for key in allowed if key in values and values[key] is not None}
    if not updates:
        return get_admin_product(product_id)
    assignments = ", ".join("{} = ?".format(key) for key in updates)
    params = [int(value) if key == "enabled" else value for key, value in updates.items()]
    params.append(product_id)
    with get_connection() as connection:
        cursor = connection.execute(
            "UPDATE products SET {}, updated_at = CURRENT_TIMESTAMP WHERE id = ?".format(assignments),
            params,
        )
    if cursor.rowcount == 0:
        return None
    return get_admin_product(product_id)


def replace_colors(product_id: str, colors: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    with get_connection() as connection:
        exists = connection.execute("SELECT 1 FROM products WHERE id = ?", (product_id,)).fetchone()
        if exists is None:
            return None
        connection.execute("DELETE FROM product_colors WHERE product_id = ?", (product_id,))
        for index, color in enumerate(colors):
            connection.execute(
                """
                INSERT INTO product_colors
                    (product_id, code, label, image_path, is_default, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    color["code"],
                    color["label"],
                    color.get("image_path"),
                    int(color.get("is_default", False)),
                    index,
                ),
            )
    return get_admin_product(product_id)


def replace_option_mappings(product_id: str, option_ids: List[str]) -> Optional[Dict[str, Any]]:
    if not option_ids:
        raise ValueError("At least one motor and voltage option is required")
    with get_connection() as connection:
        exists = connection.execute("SELECT 1 FROM products WHERE id = ?", (product_id,)).fetchone()
        if exists is None:
            return None
        placeholders = ",".join("?" for _ in option_ids)
        option_rows = connection.execute(
            "SELECT id, category_id, code FROM options WHERE id IN ({}) AND enabled = 1".format(placeholders),
            option_ids,
        ).fetchall()
        if len(option_rows) != len(set(option_ids)):
            raise ValueError("One or more options do not exist")

        categories = {row["category_id"] for row in option_rows}
        if "motor" not in categories or "voltage" not in categories:
            raise ValueError("Each product requires at least one motor and voltage option")

        existing_rows = connection.execute(
            """
            SELECT option_id, description_override, description_override_en, image_override, price_override
            FROM product_options WHERE product_id = ?
            """,
            (product_id,),
        ).fetchall()
        existing_overrides = {row["option_id"]: dict(row) for row in existing_rows}
        connection.execute("DELETE FROM product_options WHERE product_id = ?", (product_id,))
        for index, row in enumerate(option_rows):
            mapping_id = "{}-{}-{}".format(product_id.upper(), row["category_id"].upper(), row["code"])
            override = existing_overrides.get(row["id"], {})
            connection.execute(
                """
                INSERT INTO product_options
                    (product_id, option_id, mapping_id, description_override, description_override_en, image_override, price_override, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    row["id"],
                    mapping_id,
                    override.get("description_override"),
                    override.get("description_override_en"),
                    override.get("image_override"),
                    override.get("price_override"),
                    index,
                ),
            )
    return get_admin_product(product_id)

def update_product_option_override(product_id: str, option_id: str, description: Optional[str] = None, description_en: Optional[str] = None, price: Optional[int] = None) -> Optional[Dict[str, Any]]:
    with get_connection() as db:
        cur = db.execute("UPDATE product_options SET description_override=?, description_override_en=?, price_override=COALESCE(?, price_override) WHERE product_id=? AND option_id=?", (description, description_en, price, product_id, option_id))
    return get_admin_product(product_id) if cur.rowcount else None
