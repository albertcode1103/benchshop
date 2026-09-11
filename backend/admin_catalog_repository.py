from typing import Any, Dict, List, Optional

from .database import get_connection
from .catalog_refactor_repository import CatalogValidationError, _item_category
from .catalog_identity import normalize_catalog_code, strip_redundant_catalog_code
import uuid


CATALOG_ROOT_IDS = ("catalog-optional", "catalog-tools", "catalog-accessories")


def _check_option_code(connection, code: str, option_id: str = "") -> None:
    duplicate = connection.execute(
        "SELECT id FROM options WHERE id <> ? AND lower(trim(code)) = lower(trim(?)) LIMIT 1",
        (option_id, code),
    ).fetchone()
    if duplicate is not None:
        raise CatalogValidationError("CATALOG_CODE_DUPLICATE", "code", {"option_id": duplicate["id"]})

def create_product(values: Dict[str, Any]) -> Dict[str, Any]:
    product_id = values["id"].strip().lower()
    with get_connection() as db:
        db.execute("INSERT INTO products(id,name,name_en,title_name,title_name_en,description,description_en,base_price,price_usd,enabled,sort_order) VALUES(?,?,?,?,?,?,?,?,?,1,(SELECT COALESCE(MAX(sort_order),-1)+1 FROM products))", (product_id, values["name"], values.get("name_en", ""), values.get("title_name", values["name"]), values.get("title_name_en", ""), values.get("description", ""), values.get("description_en", ""), int(values.get("base_price", 0)), int(values.get("price_usd", 0))))
        db.execute("UPDATE products SET visible_zh=?,visible_en=? WHERE id=?", (int(values.get("visible_zh", True)), int(values.get("visible_en", True)), product_id))
        db.execute("INSERT INTO product_colors(product_id,code,label,label_en,is_default,sort_order) VALUES(?,?,?,?,?,0)", (product_id, "Green", "绿色", "Green", 1))
    return get_admin_product(product_id)


def list_config_categories() -> List[Dict[str, Any]]:
    with get_connection() as connection:
        categories = connection.execute(
            """
            SELECT id, name, name_en, description, description_en, multiple, sort_order, version
            FROM categories
            WHERE id NOT IN (?, ?, ?) AND catalog_type NOT IN ('tools', 'accessories')
            ORDER BY sort_order, name
            """,
            CATALOG_ROOT_IDS,
        ).fetchall()
        result = []
        for category in categories:
            item = dict(category); item["multiple"] = bool(item["multiple"])
            item["options"] = [dict(row) for row in connection.execute("SELECT id, code, name, name_en, image_path, description, description_en, notes, price, price_usd, enabled, sort_order, version FROM options WHERE category_id = ? AND deleted_at IS NULL ORDER BY sort_order, name", (item["id"],)).fetchall()]
            for option in item["options"]: option["enabled"] = bool(option["enabled"])
            result.append(item)
    return result


def update_config_option(option_id: str, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if values.get("version") is None:
        raise CatalogValidationError("CATALOG_VERSION_CONFLICT", "version")
    values = dict(values)
    with get_connection() as connection:
        current = connection.execute("SELECT code FROM options WHERE id = ? AND deleted_at IS NULL", (option_id,)).fetchone()
    if current is None:
        return None
    code = normalize_catalog_code(values.get("code") if values.get("code") is not None else current["code"])
    if "code" in values and values["code"] is not None:
        values["code"] = code
    for field in ("name", "name_en"):
        if field in values and values[field] is not None:
            values[field] = strip_redundant_catalog_code(values[field], code)
    if not code:
        raise CatalogValidationError("CATALOG_CODE_REQUIRED", "code")
    if values.get("name") == "":
        raise CatalogValidationError("CATALOG_TRANSLATION_REQUIRED", "name")
    allowed = ("code", "name", "name_en", "image_path", "description", "description_en", "notes", "price", "price_usd", "enabled", "sort_order")
    updates = {key: values[key] for key in allowed if key in values and values[key] is not None}
    if not updates: return None
    assignments = ", ".join("{} = ?".format(key) for key in updates)
    params = [int(v) if key == "enabled" else v for key, v in updates.items()]; params.extend((option_id, values["version"]))
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _check_option_code(connection, code, option_id)
        row = connection.execute("UPDATE options SET {}, version = version + 1 WHERE id = ? AND version = ? AND deleted_at IS NULL".format(assignments), params)
        if row.rowcount == 0:
            exists = connection.execute("SELECT 1 FROM options WHERE id = ? AND deleted_at IS NULL", (option_id,)).fetchone()
            if exists is None: return None
            raise CatalogValidationError("CATALOG_VERSION_CONFLICT", "version")
        result = connection.execute("SELECT id, category_id, code, name, name_en, image_path, description, description_en, notes, price, price_usd, enabled, sort_order, version FROM options WHERE id = ?", (option_id,)).fetchone()
    item = dict(result); item["enabled"] = bool(item["enabled"]); return item


def create_config_category(name: str, description: str = "", multiple: bool = True, name_en: str = "", description_en: str = "") -> Dict[str, Any]:
    category_id = uuid.uuid4().hex[:12]
    with get_connection() as connection:
        sort_order = connection.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM categories").fetchone()[0]
        connection.execute("INSERT INTO categories (id, name, name_en, description, description_en, multiple, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?)", (category_id, name.strip(), name_en.strip(), description.strip(), description_en.strip(), int(multiple), sort_order))
    return {"id": category_id, "name": name.strip(), "name_en": name_en.strip(), "description": description.strip(), "description_en": description_en.strip(), "multiple": bool(multiple), "options": [], "version": 1}


def create_config_option(category_id: str, code: str, name: str, **values: Any) -> Dict[str, Any]:
    code = normalize_catalog_code(code)
    name = strip_redundant_catalog_code(name, code)
    values["name_en"] = strip_redundant_catalog_code(values.get("name_en"), code)
    if not code:
        raise CatalogValidationError("CATALOG_CODE_REQUIRED", "code")
    if not name:
        raise CatalogValidationError("CATALOG_TRANSLATION_REQUIRED", "name")
    option_id = "opt-" + uuid.uuid4().hex[:16]
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        category = connection.execute("SELECT catalog_type FROM categories WHERE id=?", (category_id,)).fetchone()
        if category is None or category["catalog_type"] in ("tools", "accessories"):
            _item_category(connection, category_id)
        _check_option_code(connection, code)
        sort_order = connection.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM options WHERE category_id = ?", (category_id,)).fetchone()[0]
        enabled = True if values.get("enabled") is None else bool(values["enabled"])
        connection.execute("INSERT INTO options (id, category_id, code, name, name_en, image_path, description, description_en, notes, price, price_usd, enabled, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (option_id, category_id, code.strip(), name.strip(), values.get("name_en") or "", values.get("image_path"), values.get("description") or "", values.get("description_en") or "", values.get("notes") or "", values.get("price") or 0, values.get("price_usd") or 0, int(enabled), sort_order))
        result = connection.execute("SELECT id, category_id, code, name, name_en, image_path, description, description_en, notes, price, price_usd, enabled, sort_order, version FROM options WHERE id = ?", (option_id,)).fetchone()
    item = dict(result); item["enabled"] = bool(item["enabled"]); return item

def update_config_category(category_id: str, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if values.get('version') is None:
        raise CatalogValidationError('CATALOG_VERSION_CONFLICT', 'version')
    updates = {k: values[k] for k in ("name", "name_en", "description", "description_en", "multiple", "sort_order") if k in values and values[k] is not None}
    if not updates: return None
    assignments = ", ".join(f"{k} = ?" for k in updates)
    params = [int(v) if k == "multiple" else v for k, v in updates.items()] + [category_id, values['version']]
    with get_connection() as connection:
        category = connection.execute("SELECT catalog_type FROM categories WHERE id=?", (category_id,)).fetchone()
        if category and category["catalog_type"] in ("tools", "accessories"):
            raise CatalogValidationError("CATALOG_CATEGORY_NOT_AVAILABLE", "category_id")
        cur = connection.execute(f"UPDATE categories SET {assignments}, version=version+1 WHERE id = ? AND version = ?", params)
        if cur.rowcount == 0 and connection.execute('SELECT 1 FROM categories WHERE id=?', (category_id,)).fetchone():
            raise CatalogValidationError('CATALOG_VERSION_CONFLICT', 'version')
    if cur.rowcount == 0: return None
    return next((x for x in list_config_categories() if x["id"] == category_id), None)


def config_option_references(option_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as connection:
        option = connection.execute("SELECT id, code, name, category_id FROM options WHERE id = ?", (option_id,)).fetchone()
        if option is None:
            return None
        products = connection.execute(
            """
            SELECT p.id, p.name, po.mapping_id
            FROM product_options po
            JOIN products p ON p.id = po.product_id
            WHERE po.option_id = ?
            ORDER BY p.sort_order, p.name
            """,
            (option_id,),
        ).fetchall()
    result = dict(option)
    result["products"] = [dict(row) for row in products]
    result["mapping_count"] = len(result["products"])
    return result


def delete_config_option(option_id: str) -> Optional[bool]:
    references = config_option_references(option_id)
    if references is None:
        return None
    if references["mapping_count"]:
        return False
    with get_connection() as connection:
        connection.execute("DELETE FROM options WHERE id = ?", (option_id,))
    return True


def config_category_references(category_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as connection:
        category = connection.execute("SELECT id, name, catalog_type FROM categories WHERE id = ?", (category_id,)).fetchone()
        if category is None:
            return None
        options = connection.execute(
            """
            SELECT o.id, o.code, o.name, COUNT(po.product_id) AS mapping_count
            FROM options o
            LEFT JOIN product_options po ON po.option_id = o.id
            WHERE o.category_id = ?
            GROUP BY o.id, o.code, o.name
            ORDER BY o.sort_order, o.name
            """,
            (category_id,),
        ).fetchall()
    result = dict(category)
    result["protected"] = category_id in ("motor", "voltage", *CATALOG_ROOT_IDS) or category["catalog_type"] in ("tools", "accessories")
    result["options"] = [dict(row) for row in options]
    result["option_count"] = len(result["options"])
    result["mapping_count"] = sum(row["mapping_count"] for row in result["options"])
    return result


def delete_config_category(category_id: str) -> Optional[bool]:
    references = config_category_references(category_id)
    if references is None:
        return None
    if references["protected"] or references["option_count"]:
        return False
    with get_connection() as connection:
        connection.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    return True


def list_admin_products() -> List[Dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, name, name_en, title_name, title_name_en, description, description_en, base_price, price_usd, enabled, sort_order,
                   created_at, updated_at, version, visible_zh, visible_en
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
                   enabled, sort_order, version,
                   created_at, updated_at
            FROM products WHERE id = ?
            """,
            (product_id,),
        ).fetchone()
        if product_row is None:
            return None

        color_rows = connection.execute(
            """
            SELECT code, label, label_en, image_path, is_default, sort_order
            FROM product_colors WHERE product_id = ? ORDER BY sort_order, code
            """,
            (product_id,),
        ).fetchall()
        option_rows = connection.execute(
            """
            SELECT o.id, o.category_id, o.code, o.name, o.name_en,
                   o.description, o.description_en, o.image_path,
                   o.price, o.price_usd, o.enabled, o.sort_order,
                   CASE WHEN po.option_id IS NULL THEN 0 ELSE 1 END AS mapped,
                   COALESCE(po.enabled, 0) AS selected,
                   po.description_override, po.description_override_en, po.image_override, po.price_override,
                   mp.base_price_cny AS motor_base_price_cny, mp.base_price_usd AS motor_base_price_usd
            FROM options o
            LEFT JOIN product_options po
              ON po.option_id = o.id AND po.product_id = ?
            LEFT JOIN product_motor_prices mp
              ON mp.motor_option_id = o.id AND mp.product_id = ?
            ORDER BY o.category_id, o.sort_order, o.name
            """,
            (product_id, product_id),
        ).fetchall()
        category_rows = connection.execute(
            "SELECT id, name, name_en, description, description_en, multiple, sort_order FROM categories ORDER BY sort_order, name"
        ).fetchall()
        specification_rows = connection.execute(
            "SELECT id, label, label_en, value, value_en, sort_order FROM product_specifications WHERE product_id = ? ORDER BY sort_order, id",
            (product_id,),
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
        option["mapped"] = bool(option["mapped"])
        option["selected"] = bool(option["selected"])
        options_by_category.setdefault(option.pop("category_id"), []).append(option)

    product["categories"] = []
    for row in category_rows:
        category = dict(row)
        category["multiple"] = bool(category["multiple"])
        category["options"] = options_by_category.get(category["id"], [])
        product["categories"].append(category)
    product["specifications"] = [dict(row) for row in specification_rows]
    return product


def update_product(product_id: str, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if values.get('version') is None:
        raise CatalogValidationError('CATALOG_VERSION_CONFLICT', 'version')
    allowed = ("name", "title_name", "name_en", "title_name_en", "description", "description_en", "base_price", "price_usd", "enabled", "sort_order")
    updates = {key: values[key] for key in allowed if key in values and values[key] is not None}
    if not updates:
        return get_admin_product(product_id)
    assignments = ", ".join("{} = ?".format(key) for key in updates)
    params = [int(value) if key == "enabled" else value for key, value in updates.items()]
    params.extend((product_id, values['version']))
    with get_connection() as connection:
        cursor = connection.execute(
            "UPDATE products SET {}, version=version+1, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND version = ?".format(assignments),
            params,
        )
        if cursor.rowcount == 0:
            if connection.execute('SELECT 1 FROM products WHERE id=?', (product_id,)).fetchone():
                raise CatalogValidationError('CATALOG_VERSION_CONFLICT', 'version')
            return None
    return get_admin_product(product_id)


def save_product_configuration(
    product_id: str,
    values: Dict[str, Any],
    colors: List[Dict[str, Any]],
    option_ids: List[str],
    option_overrides: Dict[str, Dict[str, Any]],
    motor_prices: Optional[Dict[str, Dict[str, Any]]] = None,
    specifications: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Save every editable part of one product in one SQLite transaction."""
    if values.get('version') is None:
        raise CatalogValidationError('CATALOG_VERSION_CONFLICT', 'version')
    allowed = ("name", "title_name", "name_en", "title_name_en", "description", "description_en", "base_price", "price_usd", "enabled", "sort_order")
    updates = {key: values[key] for key in allowed if key in values and values[key] is not None}
    option_ids = list(dict.fromkeys(str(option_id).strip() for option_id in option_ids if str(option_id).strip()))
    if not option_ids:
        raise ValueError("设备至少需要保留一个电机和一个供电配置")

    with get_connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        if connection.execute("SELECT 1 FROM products WHERE id = ?", (product_id,)).fetchone() is None:
            return None

        changed = connection.execute('UPDATE products SET version=version+1 WHERE id=? AND version=?',
                                     (product_id, values['version']))
        if changed.rowcount != 1:
            raise CatalogValidationError('CATALOG_VERSION_CONFLICT', 'version')

        # A catalog option can be removed while another browser tab is editing
        # this product. Only remove dangling mappings; valid disabled mappings
        # remain because they can legitimately retain a product-specific note.
        connection.execute("DELETE FROM product_options WHERE product_id = ? AND option_id NOT IN (SELECT id FROM options)", (product_id,))
        connection.execute("DELETE FROM product_motor_prices WHERE product_id = ? AND motor_option_id NOT IN (SELECT id FROM options)", (product_id,))

        placeholders = ",".join("?" for _ in option_ids)
        option_rows = connection.execute(
            "SELECT id, category_id, code FROM options WHERE id IN ({}) AND enabled = 1".format(placeholders),
            option_ids,
        ).fetchall()
        if len(option_rows) != len(option_ids):
            existing_ids = {row["id"] for row in option_rows}
            missing_ids = [option_id for option_id in option_ids if option_id not in existing_ids]
            raise ValueError("以下配置已从配置目录移除或已停用，请刷新设备编辑页后重新选择：{}".format(", ".join(missing_ids)))
        categories = {row["category_id"] for row in option_rows}
        if "motor" not in categories or "voltage" not in categories:
            raise ValueError("设备至少需要保留一个电机和一个供电配置")

        if updates:
            assignments = ", ".join("{} = ?".format(key) for key in updates)
            params = [int(value) if key == "enabled" else value for key, value in updates.items()] + [product_id]
            connection.execute("UPDATE products SET {}, updated_at = CURRENT_TIMESTAMP WHERE id = ?".format(assignments), params)

        connection.execute("DELETE FROM product_colors WHERE product_id = ?", (product_id,))
        for index, color in enumerate(colors):
            connection.execute(
                "INSERT INTO product_colors (product_id, code, label, label_en, image_path, is_default, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (product_id, color["code"], color["label"], color.get("label_en") or color["label"], color.get("image_path"), int(color.get("is_default", False)), index),
            )

        override_ids = set(option_overrides)
        if override_ids:
            override_placeholders = ",".join("?" for _ in override_ids)
            valid_override_ids = {
                row["id"] for row in connection.execute(
                    "SELECT id FROM options WHERE id IN ({})".format(override_placeholders),
                    tuple(override_ids),
                ).fetchall()
            }
            if valid_override_ids != override_ids:
                missing_ids = sorted(override_ids - valid_override_ids)
                raise ValueError("以下专有标注对应的配置已被删除，请刷新后重新保存：{}".format(", ".join(missing_ids)))

        existing_rows = connection.execute(
            """SELECT option_id, mapping_id, description_override, description_override_en,
                      image_override, price_override, sort_order
               FROM product_options WHERE product_id = ?""",
            (product_id,),
        ).fetchall()
        existing = {row["option_id"]: dict(row) for row in existing_rows}
        selected = {row["id"]: dict(row) for row in option_rows}

        motor_prices = motor_prices or {}
        for motor_id, price in motor_prices.items():
            if int(price.get("base_price_cny", 0)) < 0 or int(price.get("base_price_usd", 0)) < 0:
                raise ValueError("Motor base prices cannot be negative")
            motor_row = connection.execute("SELECT id FROM options WHERE id = ? AND category_id = 'motor'", (motor_id,)).fetchone()
            if motor_row is None or motor_id not in selected:
                raise ValueError("Motor price must reference a selected motor")
            connection.execute(
                "INSERT INTO product_motor_prices (product_id, motor_option_id, base_price_cny, base_price_usd, updated_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP) ON CONFLICT(product_id, motor_option_id) DO UPDATE SET base_price_cny=excluded.base_price_cny, base_price_usd=excluded.base_price_usd, updated_at=CURRENT_TIMESTAMP",
                (product_id, motor_id, int(price.get("base_price_cny", 0)), int(price.get("base_price_usd", 0))),
            )
        motor_option_ids = [row["id"] for row in option_rows if row["category_id"] == "motor"]
        connection.execute("DELETE FROM product_motor_prices WHERE product_id = ? AND motor_option_id NOT IN ({})".format(",".join("?" for _ in motor_option_ids)), [product_id] + motor_option_ids)

        if specifications is not None:
            connection.execute("DELETE FROM product_specifications WHERE product_id = ?", (product_id,))
            for index, spec in enumerate(specifications):
                label = str(spec.get("label") or "").strip()
                label_en = str(spec.get("label_en") or "").strip()
                value = str(spec.get("value") or "").strip()
                value_en = str(spec.get("value_en") or "").strip()
                if not any((label, label_en, value, value_en)):
                    continue
                connection.execute(
                    "INSERT INTO product_specifications (id, product_id, label, label_en, value, value_en, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (str(spec.get("id") or uuid.uuid4().hex), product_id, label, label_en, value, value_en, int(spec.get("sort_order", index))),
                )

        all_option_ids = set(existing) | set(selected) | override_ids
        option_meta = {
            row["id"]: dict(row) for row in connection.execute(
                "SELECT id, category_id, code FROM options WHERE id IN ({})".format(
                    ",".join("?" for _ in all_option_ids)
                ),
                tuple(all_option_ids),
            ).fetchall()
        } if all_option_ids else {}
        for index, option_id in enumerate(sorted(all_option_ids, key=lambda value: (0 if value in selected else 1, value))):
            override = option_overrides.get(option_id)
            previous = existing.get(option_id, {})
            meta = option_meta[option_id]
            mapping_id = previous.get("mapping_id") or "{}-{}-{}".format(product_id.upper(), meta["category_id"].upper(), meta["code"])
            description = override.get("description_override") if override is not None else previous.get("description_override")
            description_en = override.get("description_override_en") if override is not None else previous.get("description_override_en")
            connection.execute(
                """INSERT INTO product_options
                   (product_id, option_id, mapping_id, description_override, description_override_en,
                    image_override, price_override, sort_order, enabled)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(product_id, option_id) DO UPDATE SET
                     mapping_id=excluded.mapping_id,
                     description_override=excluded.description_override,
                     description_override_en=excluded.description_override_en,
                     image_override=excluded.image_override,
                     price_override=excluded.price_override,
                     sort_order=excluded.sort_order,
                     enabled=excluded.enabled""",
                (
                    product_id, option_id, mapping_id, description, description_en,
                    previous.get("image_override"), previous.get("price_override"), index,
                    int(option_id in selected),
                ),
            )
    return get_admin_product(product_id)


def replace_colors(product_id: str, colors: List[Dict[str, Any]], version: Optional[int] = None) -> Optional[Dict[str, Any]]:
    if version is None:
        raise CatalogValidationError('CATALOG_VERSION_CONFLICT', 'version')
    with get_connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        exists = connection.execute("SELECT 1 FROM products WHERE id = ?", (product_id,)).fetchone()
        if exists is None:
            return None
        changed = connection.execute('UPDATE products SET version=version+1,updated_at=CURRENT_TIMESTAMP WHERE id=? AND version=?', (product_id, version))
        if changed.rowcount != 1:
            raise CatalogValidationError('CATALOG_VERSION_CONFLICT', 'version')
        connection.execute("DELETE FROM product_colors WHERE product_id = ?", (product_id,))
        for index, color in enumerate(colors):
            connection.execute(
                """
                INSERT INTO product_colors
                    (product_id, code, label, label_en, image_path, is_default, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    color["code"],
                    color["label"],
                    color.get("label_en") or color["label"],
                    color.get("image_path"),
                    int(color.get("is_default", False)),
                    index,
                ),
            )
    return get_admin_product(product_id)


def replace_option_mappings(product_id: str, option_ids: List[str], version: Optional[int] = None) -> Optional[Dict[str, Any]]:
    if version is None:
        raise CatalogValidationError('CATALOG_VERSION_CONFLICT', 'version')
    option_ids = list(dict.fromkeys(str(option_id).strip() for option_id in option_ids if str(option_id).strip()))
    if not option_ids:
        raise ValueError("设备至少需要保留一个电机和一个供电配置")
    with get_connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        exists = connection.execute("SELECT 1 FROM products WHERE id = ?", (product_id,)).fetchone()
        if exists is None:
            return None
        changed = connection.execute('UPDATE products SET version=version+1,updated_at=CURRENT_TIMESTAMP WHERE id=? AND version=?', (product_id, version))
        if changed.rowcount != 1:
            raise CatalogValidationError('CATALOG_VERSION_CONFLICT', 'version')
        placeholders = ",".join("?" for _ in option_ids)
        option_rows = connection.execute(
            "SELECT id, category_id, code FROM options WHERE id IN ({}) AND enabled = 1".format(placeholders),
            option_ids,
        ).fetchall()
        if len(option_rows) != len(option_ids):
            existing_ids = {row["id"] for row in option_rows}
            missing_ids = [option_id for option_id in option_ids if option_id not in existing_ids]
            raise ValueError("以下配置已从配置目录移除或已停用，请刷新设备编辑页后重新选择：{}".format(", ".join(missing_ids)))

        categories = {row["category_id"] for row in option_rows}
        if "motor" not in categories or "voltage" not in categories:
            raise ValueError("设备至少需要保留一个电机和一个供电配置")

        existing_rows = connection.execute(
            """
            SELECT option_id, description_override, description_override_en, image_override, price_override
            FROM product_options WHERE product_id = ?
            """,
            (product_id,),
        ).fetchall()
        existing_overrides = {row["option_id"]: dict(row) for row in existing_rows}
        connection.execute("UPDATE product_options SET enabled = 0 WHERE product_id = ?", (product_id,))
        for index, row in enumerate(option_rows):
            mapping_id = "{}-{}-{}".format(product_id.upper(), row["category_id"].upper(), row["code"])
            override = existing_overrides.get(row["id"], {})
            connection.execute(
                """
                INSERT INTO product_options
                    (product_id, option_id, mapping_id, description_override, description_override_en, image_override, price_override, sort_order, enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(product_id, option_id) DO UPDATE SET
                    mapping_id=excluded.mapping_id,
                    description_override=excluded.description_override,
                    description_override_en=excluded.description_override_en,
                    image_override=excluded.image_override,
                    price_override=excluded.price_override,
                    sort_order=excluded.sort_order,
                    enabled=1
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

def update_product_option_override(product_id: str, option_id: str, description: Optional[str] = None, description_en: Optional[str] = None, price: Optional[int] = None, *, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
    if version is None:
        raise CatalogValidationError('CATALOG_VERSION_CONFLICT', 'version')
    with get_connection() as db:
        db.execute('BEGIN IMMEDIATE')
        product_exists = db.execute("SELECT 1 FROM products WHERE id=?", (product_id,)).fetchone()
        option = db.execute("SELECT id, category_id, code FROM options WHERE id=?", (option_id,)).fetchone()
        if product_exists is None or option is None:
            return None
        changed = db.execute('UPDATE products SET version=version+1,updated_at=CURRENT_TIMESTAMP WHERE id=? AND version=?', (product_id, version))
        if changed.rowcount != 1:
            raise CatalogValidationError('CATALOG_VERSION_CONFLICT', 'version')
        mapping_id = "{}-{}-{}".format(product_id.upper(), option["category_id"].upper(), option["code"])
        description = description.strip() if description else None
        description_en = description_en.strip() if description_en else None
        db.execute(
            """INSERT INTO product_options
               (product_id, option_id, mapping_id, description_override, description_override_en, price_override, enabled)
               VALUES (?, ?, ?, ?, ?, ?, 0)
               ON CONFLICT(product_id, option_id) DO UPDATE SET
                 description_override=excluded.description_override,
                 description_override_en=excluded.description_override_en,
                 price_override=COALESCE(excluded.price_override, product_options.price_override)""",
            (product_id, option_id, mapping_id, description, description_en, price),
        )
    return get_admin_product(product_id)
