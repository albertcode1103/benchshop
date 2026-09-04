"""Persistence and validation for the refactored device/catalog editor."""

import re
import uuid
from typing import Any, Dict, List, Optional, Sequence

from .database import get_connection
from .media_routes import validate_media_reference


BASE_OPTION_TYPES = ("motor", "power", "channel")
TRANSLATION_STATUSES = ("missing", "machine_draft", "reviewed")
DISPLAY_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
CATALOG_ROOTS = {
    "catalog-optional": "optional",
    "catalog-tools": "tools",
    "catalog-accessories": "accessories",
}


class CatalogValidationError(ValueError):
    def __init__(self, code: str, field: str = "", params: Optional[Dict[str, Any]] = None):
        self.code = code
        self.field = field
        self.params = params or {}
        super().__init__(code)


def _dicts(rows) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows]


def get_catalog_tree(include_disabled: bool = True) -> List[Dict[str, Any]]:
    where = "" if include_disabled else "WHERE c.enabled = 1"
    with get_connection() as db:
        categories = _dicts(
            db.execute(
                """
                SELECT c.id, c.parent_id, c.catalog_type, c.name, c.name_en,
                       c.description, c.description_en, c.multiple, c.enabled,
                       c.sort_order, c.version, c.translation_status
                FROM categories c
                {}
                ORDER BY
                    CASE c.catalog_type
                        WHEN 'optional' THEN 0
                        WHEN 'tools' THEN 1
                        WHEN 'accessories' THEN 2
                        ELSE 9
                    END,
                    c.sort_order, c.id
                """.format(where)
            ).fetchall()
        )
        options = _dicts(
            db.execute(
                """
                SELECT o.id, o.category_id, o.code, o.name, o.name_en,
                       o.description, o.description_en, o.notes, o.note_en,
                       o.image_path, o.price, o.price_usd, o.enabled,
                       o.sort_order, o.version, o.translation_status
                FROM options o
                JOIN categories c ON c.id = o.category_id
                WHERE o.deleted_at IS NULL
                  AND (? = 1 OR (o.enabled = 1 AND c.enabled = 1))
                  AND c.catalog_type IN ('optional', 'tools', 'accessories')
                ORDER BY o.sort_order, o.id
                """,
                (int(include_disabled),),
            ).fetchall()
        )

    options_by_category: Dict[str, List[Dict[str, Any]]] = {}
    for item in options:
        item["enabled"] = bool(item["enabled"])
        options_by_category.setdefault(item["category_id"], []).append(item)

    nodes: Dict[str, Dict[str, Any]] = {}
    for category in categories:
        category["enabled"] = bool(category["enabled"])
        category["children"] = []
        category["options"] = options_by_category.get(category["id"], [])
        nodes[category["id"]] = category

    roots: List[Dict[str, Any]] = []
    for category in categories:
        parent = nodes.get(category.get("parent_id"))
        if parent is None:
            if category["catalog_type"] != "legacy_basic":
                roots.append(category)
        else:
            parent["children"].append(category)
    return roots


def _translation_status(value: Any, *, english_value: str, field: str) -> str:
    status = str(value or ("machine_draft" if english_value else "missing"))
    if status not in TRANSLATION_STATUSES:
        raise CatalogValidationError("CATALOG_TRANSLATION_STATUS_INVALID", field)
    if status == "reviewed" and not english_value:
        raise CatalogValidationError("CATALOG_TRANSLATION_REQUIRED", field)
    return status


def _catalog_category_row(db, category_id: str):
    return db.execute(
        """
        SELECT id, parent_id, catalog_type, name, name_en, description,
               description_en, multiple, enabled, sort_order, version,
               translation_status
        FROM categories WHERE id = ?
        """,
        (category_id,),
    ).fetchone()


def _catalog_item_row(db, option_id: str):
    return db.execute(
        """
        SELECT o.id, o.category_id, c.catalog_type, o.code, o.name,
               o.name_en, o.description, o.description_en, o.notes,
               o.note_en, o.image_path, o.image_width, o.image_height,
               o.price, o.price_usd, o.enabled, o.sort_order, o.version,
               o.deleted_at, o.translation_status
        FROM options o
        JOIN categories c ON c.id = o.category_id
        WHERE o.id = ?
        """,
        (option_id,),
    ).fetchone()


def _item_category(db, category_id: str):
    category = _catalog_category_row(db, category_id)
    if category is None:
        raise CatalogValidationError("CATALOG_CATEGORY_NOT_FOUND", "category_id")
    if not bool(category["enabled"]) or category["catalog_type"] not in ("optional", "tools", "accessories"):
        raise CatalogValidationError("CATALOG_CATEGORY_NOT_AVAILABLE", "category_id")
    child = db.execute(
        "SELECT 1 FROM categories WHERE parent_id = ? LIMIT 1", (category_id,)
    ).fetchone()
    if child is not None:
        raise CatalogValidationError("CATALOG_CATEGORY_NOT_LEAF", "category_id")
    return category


def create_catalog_category(
    *,
    parent_id: str,
    name_zh: str,
    name_en: str,
    description_zh: str = "",
    description_en: str = "",
    enabled: bool = True,
    sort_order: int = 0,
    translation_status: str = "machine_draft",
) -> Dict[str, Any]:
    name_zh = name_zh.strip()
    name_en = name_en.strip()
    if not name_zh or (enabled and not name_en):
        raise CatalogValidationError("CATALOG_TRANSLATION_REQUIRED", "name")
    if parent_id != "catalog-optional":
        raise CatalogValidationError("CATALOG_CATEGORY_PARENT_INVALID", "parent_id")
    status = _translation_status(translation_status, english_value=name_en, field="translation_status")
    category_id = "category-{}".format(uuid.uuid4().hex)
    with get_connection() as db:
        parent = _catalog_category_row(db, parent_id)
        if parent is None or parent["catalog_type"] != "optional" or not bool(parent["enabled"]):
            raise CatalogValidationError("CATALOG_CATEGORY_PARENT_INVALID", "parent_id")
        duplicate = db.execute(
            """
            SELECT id FROM categories
            WHERE parent_id = ? AND lower(trim(name)) = lower(trim(?))
            LIMIT 1
            """,
            (parent_id, name_zh),
        ).fetchone()
        if duplicate is not None:
            raise CatalogValidationError("CATALOG_CATEGORY_DUPLICATE", "name", {"category_id": duplicate["id"]})
        db.execute(
            """
            INSERT INTO categories
                (id, name, name_en, description, description_en, multiple,
                 sort_order, parent_id, catalog_type, enabled, version,
                 translation_status)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, 'optional', ?, 1, ?)
            """,
            (
                category_id,
                name_zh,
                name_en,
                description_zh.strip(),
                description_en.strip(),
                int(sort_order),
                parent_id,
                int(enabled),
                status,
            ),
        )
        result = _catalog_category_row(db, category_id)
    item = dict(result)
    item["enabled"] = bool(item["enabled"])
    return item


def update_catalog_category_v2(
    category_id: str,
    *,
    version: int,
    name_zh: str,
    name_en: str,
    description_zh: str = "",
    description_en: str = "",
    enabled: bool = True,
    sort_order: int = 0,
    translation_status: str = "machine_draft",
) -> Dict[str, Any]:
    if category_id in CATALOG_ROOTS:
        raise CatalogValidationError("CATALOG_CATEGORY_PROTECTED", "category_id")
    name_zh = name_zh.strip()
    name_en = name_en.strip()
    if not name_zh or (enabled and not name_en):
        raise CatalogValidationError("CATALOG_TRANSLATION_REQUIRED", "name")
    with get_connection() as db:
        current = _catalog_category_row(db, category_id)
        if current is None:
            raise CatalogValidationError("CATALOG_CATEGORY_NOT_FOUND", "category_id")
        if int(current["version"]) != int(version):
            raise CatalogValidationError(
                "CATALOG_VERSION_CONFLICT",
                "version",
                {"current_version": int(current["version"])},
            )
        if current["parent_id"] != "catalog-optional" or current["catalog_type"] != "optional":
            raise CatalogValidationError("CATALOG_CATEGORY_PROTECTED", "category_id")
        duplicate = db.execute(
            """
            SELECT id FROM categories
            WHERE id <> ? AND parent_id = ?
              AND lower(trim(name)) = lower(trim(?))
            LIMIT 1
            """,
            (category_id, current["parent_id"], name_zh),
        ).fetchone()
        if duplicate is not None:
            raise CatalogValidationError("CATALOG_CATEGORY_DUPLICATE", "name", {"category_id": duplicate["id"]})
        status = _translation_status(translation_status, english_value=name_en, field="translation_status")
        chinese_changed = (
            current["name"] != name_zh
            or current["description"] != description_zh.strip()
        )
        english_unchanged = (
            current["name_en"] == name_en
            and current["description_en"] == description_en.strip()
        )
        if chinese_changed and english_unchanged and status == "reviewed":
            status = "machine_draft"
        db.execute(
            """
            UPDATE categories
            SET name = ?, name_en = ?, description = ?, description_en = ?,
                enabled = ?, sort_order = ?, translation_status = ?,
                version = version + 1
            WHERE id = ? AND version = ?
            """,
            (
                name_zh,
                name_en,
                description_zh.strip(),
                description_en.strip(),
                int(enabled),
                int(sort_order),
                status,
                category_id,
                version,
            ),
        )
        result = _catalog_category_row(db, category_id)
    item = dict(result)
    item["enabled"] = bool(item["enabled"])
    return item


def delete_catalog_category_v2(category_id: str) -> None:
    if category_id in CATALOG_ROOTS:
        raise CatalogValidationError("CATALOG_CATEGORY_PROTECTED", "category_id")
    with get_connection() as db:
        current = _catalog_category_row(db, category_id)
        if current is None:
            raise CatalogValidationError("CATALOG_CATEGORY_NOT_FOUND", "category_id")
        child_count = db.execute(
            "SELECT COUNT(*) FROM categories WHERE parent_id = ?", (category_id,)
        ).fetchone()[0]
        option_count = db.execute(
            "SELECT COUNT(*) FROM options WHERE category_id = ?", (category_id,)
        ).fetchone()[0]
        if child_count or option_count:
            raise CatalogValidationError(
                "CATALOG_CATEGORY_NOT_EMPTY",
                "category_id",
                {"child_count": child_count, "option_count": option_count},
            )
        db.execute("DELETE FROM categories WHERE id = ?", (category_id,))


def create_catalog_item(
    *,
    category_id: str,
    code: str,
    name_zh: str,
    name_en: str,
    description_zh: str = "",
    description_en: str = "",
    note_zh: str = "",
    note_en: str = "",
    image_path: Optional[str] = None,
    image_width: Optional[int] = None,
    image_height: Optional[int] = None,
    price_cny: int = 0,
    price_usd: int = 0,
    enabled: bool = True,
    sort_order: int = 0,
    translation_status: str = "machine_draft",
) -> Dict[str, Any]:
    code = code.strip()
    name_zh = name_zh.strip()
    name_en = name_en.strip()
    if not code:
        raise CatalogValidationError("CATALOG_CODE_REQUIRED", "code")
    if not name_zh or (enabled and not name_en):
        raise CatalogValidationError("CATALOG_TRANSLATION_REQUIRED", "name")
    if int(price_cny) < 0 or int(price_usd) < 0:
        raise CatalogValidationError("CATALOG_PRICE_INVALID", "price")
    if image_width is not None and int(image_width) <= 0:
        raise CatalogValidationError("PRODUCT_IMAGE_SIZE_INVALID", "image")
    if image_height is not None and int(image_height) <= 0:
        raise CatalogValidationError("PRODUCT_IMAGE_SIZE_INVALID", "image")
    if not validate_media_reference(image_path):
        raise CatalogValidationError("CATALOG_MEDIA_NOT_FOUND", "image_path")
    status = _translation_status(translation_status, english_value=name_en, field="translation_status")
    option_id = "opt-{}".format(uuid.uuid4().hex)
    with get_connection() as db:
        _item_category(db, category_id)
        duplicate = db.execute(
            "SELECT id FROM options WHERE lower(trim(code)) = lower(trim(?)) LIMIT 1",
            (code,),
        ).fetchone()
        if duplicate is not None:
            raise CatalogValidationError("CATALOG_CODE_DUPLICATE", "code", {"option_id": duplicate["id"]})
        db.execute(
            """
            INSERT INTO options
                (id, category_id, code, name, name_en, description,
                 description_en, notes, note_en, image_path, image_width,
                 image_height, price, price_usd, enabled, sort_order,
                 version, deleted_at, translation_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, NULL, ?)
            """,
            (
                option_id,
                category_id,
                code,
                name_zh,
                name_en,
                description_zh.strip(),
                description_en.strip(),
                note_zh.strip(),
                note_en.strip(),
                image_path,
                int(image_width) if image_width is not None else None,
                int(image_height) if image_height is not None else None,
                int(price_cny),
                int(price_usd),
                int(enabled),
                int(sort_order),
                status,
            ),
        )
        result = _catalog_item_row(db, option_id)
    item = dict(result)
    item["enabled"] = bool(item["enabled"])
    return item


def update_catalog_item(
    option_id: str,
    *,
    version: int,
    category_id: str,
    code: str,
    name_zh: str,
    name_en: str,
    description_zh: str = "",
    description_en: str = "",
    note_zh: str = "",
    note_en: str = "",
    image_path: Optional[str] = None,
    image_width: Optional[int] = None,
    image_height: Optional[int] = None,
    price_cny: int = 0,
    price_usd: int = 0,
    enabled: bool = True,
    sort_order: int = 0,
    translation_status: str = "machine_draft",
) -> Dict[str, Any]:
    code = code.strip()
    name_zh = name_zh.strip()
    name_en = name_en.strip()
    if not code:
        raise CatalogValidationError("CATALOG_CODE_REQUIRED", "code")
    if not name_zh or (enabled and not name_en):
        raise CatalogValidationError("CATALOG_TRANSLATION_REQUIRED", "name")
    if int(price_cny) < 0 or int(price_usd) < 0:
        raise CatalogValidationError("CATALOG_PRICE_INVALID", "price")
    if image_width is not None and int(image_width) <= 0:
        raise CatalogValidationError("PRODUCT_IMAGE_SIZE_INVALID", "image")
    if image_height is not None and int(image_height) <= 0:
        raise CatalogValidationError("PRODUCT_IMAGE_SIZE_INVALID", "image")
    if not validate_media_reference(image_path):
        raise CatalogValidationError("CATALOG_MEDIA_NOT_FOUND", "image_path")
    status = _translation_status(translation_status, english_value=name_en, field="translation_status")
    with get_connection() as db:
        current = _catalog_item_row(db, option_id)
        if current is None or current["deleted_at"] is not None:
            raise CatalogValidationError("CATALOG_ITEM_NOT_FOUND", "option_id")
        if int(current["version"]) != int(version):
            raise CatalogValidationError(
                "CATALOG_VERSION_CONFLICT",
                "version",
                {"current_version": int(current["version"])},
            )
        category = _item_category(db, category_id)
        if current["catalog_type"] != category["catalog_type"]:
            references = db.execute(
                "SELECT 1 FROM product_options WHERE option_id = ? LIMIT 1", (option_id,)
            ).fetchone()
            if references is not None:
                raise CatalogValidationError("CATALOG_ITEM_TYPE_CHANGE_FORBIDDEN", "category_id")
        duplicate = db.execute(
            """
            SELECT id FROM options
            WHERE id <> ? AND lower(trim(code)) = lower(trim(?))
            LIMIT 1
            """,
            (option_id, code),
        ).fetchone()
        if duplicate is not None:
            raise CatalogValidationError("CATALOG_CODE_DUPLICATE", "code", {"option_id": duplicate["id"]})
        chinese_changed = (
            current["name"] != name_zh
            or current["description"] != description_zh.strip()
            or current["notes"] != note_zh.strip()
        )
        english_unchanged = (
            current["name_en"] == name_en
            and current["description_en"] == description_en.strip()
            and current["note_en"] == note_en.strip()
        )
        if chinese_changed and english_unchanged and status == "reviewed":
            status = "machine_draft"
        db.execute(
            """
            UPDATE options
            SET category_id = ?, code = ?, name = ?, name_en = ?,
                description = ?, description_en = ?, notes = ?, note_en = ?,
                image_path = ?, image_width = ?, image_height = ?, price = ?,
                price_usd = ?, enabled = ?, sort_order = ?,
                translation_status = ?, version = version + 1
            WHERE id = ? AND version = ? AND deleted_at IS NULL
            """,
            (
                category_id,
                code,
                name_zh,
                name_en,
                description_zh.strip(),
                description_en.strip(),
                note_zh.strip(),
                note_en.strip(),
                image_path,
                int(image_width) if image_width is not None else None,
                int(image_height) if image_height is not None else None,
                int(price_cny),
                int(price_usd),
                int(enabled),
                int(sort_order),
                status,
                option_id,
                version,
            ),
        )
        result = _catalog_item_row(db, option_id)
    item = dict(result)
    item["enabled"] = bool(item["enabled"])
    return item


def reorder_catalog_items(category_id: str, items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Atomically replace the complete order of one catalog category."""
    submitted_ids = [str(item.get("id") or "") for item in items]
    if not submitted_ids or len(submitted_ids) != len(set(submitted_ids)):
        raise CatalogValidationError("CATALOG_ORDER_INVALID", "items")
    with get_connection() as db:
        _item_category(db, category_id)
        current_rows = db.execute(
            "SELECT id, version FROM options WHERE category_id = ? AND deleted_at IS NULL ORDER BY sort_order, id",
            (category_id,),
        ).fetchall()
        current = {row["id"]: int(row["version"]) for row in current_rows}
        if set(submitted_ids) != set(current):
            raise CatalogValidationError("CATALOG_ORDER_INVALID", "items")
        for index, item in enumerate(items):
            option_id = str(item.get("id") or "")
            version = int(item.get("version") or 0)
            if current[option_id] != version:
                raise CatalogValidationError(
                    "CATALOG_VERSION_CONFLICT", "version", {"current_version": current[option_id]}
                )
            cursor = db.execute(
                "UPDATE options SET sort_order = ?, version = version + 1 WHERE id = ? AND version = ?",
                (index, option_id, version),
            )
            if cursor.rowcount != 1:
                raise CatalogValidationError("CATALOG_VERSION_CONFLICT", "version")
        result = [_catalog_item_row(db, option_id) for option_id in submitted_ids]
    return [dict(row) for row in result if row is not None]


def disable_catalog_item(option_id: str, *, version: int) -> Dict[str, Any]:
    with get_connection() as db:
        current = _catalog_item_row(db, option_id)
        if current is None or current["deleted_at"] is not None:
            raise CatalogValidationError("CATALOG_ITEM_NOT_FOUND", "option_id")
        if int(current["version"]) != int(version):
            raise CatalogValidationError(
                "CATALOG_VERSION_CONFLICT",
                "version",
                {"current_version": int(current["version"])},
            )
        db.execute(
            "UPDATE options SET enabled = 0, version = version + 1 WHERE id = ? AND version = ?",
            (option_id, version),
        )
        result = _catalog_item_row(db, option_id)
    item = dict(result)
    item["enabled"] = bool(item["enabled"])
    return item


def delete_catalog_item(option_id: str, *, version: int) -> Dict[str, Any]:
    with get_connection() as db:
        current = _catalog_item_row(db, option_id)
        if current is None or current["deleted_at"] is not None:
            raise CatalogValidationError("CATALOG_ITEM_NOT_FOUND", "option_id")
        if int(current["version"]) != int(version):
            raise CatalogValidationError(
                "CATALOG_VERSION_CONFLICT",
                "version",
                {"current_version": int(current["version"])},
            )
        product_count = db.execute(
            "SELECT COUNT(*) FROM product_options WHERE option_id = ?", (option_id,)
        ).fetchone()[0]
        cart_count = db.execute(
            "SELECT COUNT(*) FROM saved_catalog_items WHERE option_id = ?", (option_id,)
        ).fetchone()[0]
        share_count = db.execute(
            "SELECT COUNT(*) FROM config_share_items WHERE source_id = ?", (option_id,)
        ).fetchone()[0]
        reference_count = int(product_count) + int(cart_count) + int(share_count)
        if reference_count:
            db.execute(
                """
                UPDATE options
                SET enabled = 0, deleted_at = CURRENT_TIMESTAMP,
                    version = version + 1
                WHERE id = ? AND version = ?
                """,
                (option_id, version),
            )
            mode = "soft"
        else:
            db.execute("DELETE FROM options WHERE id = ? AND version = ?", (option_id, version))
            mode = "hard"
    return {
        "id": option_id,
        "mode": mode,
        "reference_count": reference_count,
        "references": {
            "products": int(product_count),
            "cart": int(cart_count),
            "shares": int(share_count),
        },
    }


def get_product_editor(product_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as db:
        product = db.execute(
            """
            SELECT id, name AS model, title_name AS product_name_zh,
                   title_name_en AS product_name_en, description AS overview_zh,
                   description_en AS overview_en, enabled, sort_order, version,
                   translation_status
            FROM products WHERE id = ?
            """,
            (product_id,),
        ).fetchone()
        if product is None:
            return None

        colors = _dicts(
            db.execute(
                """
                SELECT code AS id, label AS name_zh, label_en AS name_en,
                       display_color, image_path, image_width, image_height,
                       is_default, enabled, sort_order, version, translation_status
                FROM product_colors
                WHERE product_id = ?
                ORDER BY sort_order, code
                """,
                (product_id,),
            ).fetchall()
        )
        groups = _dicts(
            db.execute(
                """
                SELECT id, option_type, required, single_select, sort_order,
                       enabled, version
                FROM product_base_option_groups
                WHERE product_id = ?
                ORDER BY sort_order, option_type
                """,
                (product_id,),
            ).fetchall()
        )
        option_rows = _dicts(
            db.execute(
                """
                SELECT o.id, o.group_id, o.name_zh, o.name_en,
                       o.price_cny_minor, o.price_usd_minor, o.price_confirmed,
                       o.is_free, o.sort_order, o.enabled, o.version,
                       o.translation_status
                FROM product_base_options o
                JOIN product_base_option_groups g ON g.id = o.group_id
                WHERE g.product_id = ?
                ORDER BY g.sort_order, o.sort_order, o.id
                """,
                (product_id,),
            ).fetchall()
        )
        variants = _dicts(
            db.execute(
                """
                SELECT id, motor_option_id, channel_option_id,
                       price_cny_minor, price_usd_minor, price_confirmed,
                       enabled, version
                FROM product_price_variants
                WHERE product_id = ?
                ORDER BY created_at, id
                """,
                (product_id,),
            ).fetchall()
        )
        specifications = _dicts(
            db.execute(
                """
                SELECT id, label, label_en, value, value_en, sort_order
                FROM product_specifications
                WHERE product_id = ?
                ORDER BY sort_order, id
                """,
                (product_id,),
            ).fetchall()
        )
        optional_ids = [
            row[0]
            for row in db.execute(
                """
                SELECT po.option_id
                FROM product_options po
                JOIN options o ON o.id = po.option_id
                JOIN categories c ON c.id = o.category_id
                WHERE po.product_id = ? AND po.enabled = 1
                  AND o.enabled = 1 AND o.deleted_at IS NULL
                  AND c.catalog_type = 'optional'
                ORDER BY po.sort_order, o.sort_order, o.id
                """,
                (product_id,),
            ).fetchall()
        ]
        optional_overrides = {
            row["option_id"]: {
                "description_override": row["description_override"],
                "description_override_en": row["description_override_en"],
            }
            for row in db.execute(
                """
                SELECT option_id, description_override, description_override_en
                FROM product_options
                WHERE product_id = ?
                """,
                (product_id,),
            ).fetchall()
        }

    options_by_group: Dict[str, List[Dict[str, Any]]] = {}
    for option in option_rows:
        for field in ("price_confirmed", "is_free", "enabled"):
            option[field] = bool(option[field])
        options_by_group.setdefault(option["group_id"], []).append(option)
    for group in groups:
        group["required"] = bool(group["required"])
        group["single_select"] = True
        group["enabled"] = bool(group["enabled"])
        group["options"] = options_by_group.get(group["id"], [])
    for color in colors:
        color["is_default"] = bool(color["is_default"])
        color["enabled"] = bool(color["enabled"])
    for variant in variants:
        variant["price_confirmed"] = bool(variant["price_confirmed"])
        variant["enabled"] = bool(variant["enabled"])

    result = dict(product)
    result["enabled"] = bool(result["enabled"])
    result["colors"] = colors
    result["base_option_groups"] = groups
    result["price_variants"] = variants
    result["optional_config_ids"] = optional_ids
    result["optional_config_overrides"] = optional_overrides
    result["specifications"] = specifications
    return result


def _validate_optional_ids(db, option_ids: Sequence[str]) -> List[Dict[str, Any]]:
    unique_ids = list(dict.fromkeys(option_ids))
    if len(unique_ids) != len(option_ids):
        raise CatalogValidationError("CATALOG_OPTION_DUPLICATE", "optional_config_ids")
    if not unique_ids:
        return []
    placeholders = ",".join("?" for _ in unique_ids)
    rows = _dicts(
        db.execute(
            """
            SELECT o.id, o.category_id, o.code
            FROM options o
            JOIN categories c ON c.id = o.category_id
            WHERE o.id IN ({})
              AND o.enabled = 1
              AND o.deleted_at IS NULL
              AND c.enabled = 1
              AND c.catalog_type = 'optional'
            """.format(placeholders),
            unique_ids,
        ).fetchall()
    )
    found = {row["id"] for row in rows}
    missing = [option_id for option_id in unique_ids if option_id not in found]
    if missing:
        raise CatalogValidationError(
            "CATALOG_OPTION_NOT_AVAILABLE",
            "optional_config_ids",
            {"option_ids": missing},
        )
    by_id = {row["id"]: row for row in rows}
    return [by_id[option_id] for option_id in unique_ids]


def save_product_editor(
    product_id: str,
    *,
    version: int,
    model: str,
    product_name_zh: str,
    product_name_en: str,
    overview_zh: str,
    overview_en: str,
    enabled: bool,
    groups: Sequence[Dict[str, Any]],
    variants: Sequence[Dict[str, Any]],
    optional_config_ids: Sequence[str],
    optional_config_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    translation_status: str = "machine_draft",
    colors: Optional[Sequence[Dict[str, Any]]] = None,
    specifications: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if not model.strip() or not product_name_zh.strip() or not product_name_en.strip():
        raise CatalogValidationError("CATALOG_REQUIRED_FIELD", "product")
    group_types = [str(group.get("option_type", "")) for group in groups]
    if len(group_types) != len(set(group_types)) or any(value not in BASE_OPTION_TYPES for value in group_types):
        raise CatalogValidationError("BASE_OPTION_GROUP_INVALID", "base_option_groups")
    if "motor" not in group_types or "power" not in group_types:
        raise CatalogValidationError("BASE_OPTION_GROUP_REQUIRED", "base_option_groups")

    optional_config_overrides = optional_config_overrides or {}
    with get_connection() as db:
        current = db.execute(
            """
            SELECT version, title_name, title_name_en, description,
                   description_en, translation_status
            FROM products WHERE id = ?
            """,
            (product_id,),
        ).fetchone()
        if current is None:
            raise CatalogValidationError("CATALOG_PRODUCT_NOT_FOUND", "product_id")
        if int(current["version"]) != int(version):
            raise CatalogValidationError(
                "CATALOG_VERSION_CONFLICT",
                "version",
                {"current_version": int(current["version"])},
            )

        duplicate_model = db.execute(
            """
            SELECT id FROM products
            WHERE id <> ? AND lower(trim(name)) = lower(trim(?))
            LIMIT 1
            """,
            (product_id, model),
        ).fetchone()
        if duplicate_model is not None:
            raise CatalogValidationError(
                "CATALOG_MODEL_DUPLICATE",
                "model",
                {"product_id": duplicate_model["id"]},
            )

        translation_status = _translation_status(
            translation_status,
            english_value=product_name_en.strip(),
            field="translation_status",
        )
        chinese_changed = (
            current["title_name"] != product_name_zh.strip()
            or current["description"] != overview_zh.strip()
        )
        english_unchanged = (
            current["title_name_en"] == product_name_en.strip()
            and current["description_en"] == overview_en.strip()
        )
        if chinese_changed and english_unchanged and translation_status == "reviewed":
            translation_status = "machine_draft"

        validated_options = _validate_optional_ids(db, optional_config_ids)
        db.execute(
            """
            UPDATE products
            SET name = ?, name_en = ?, title_name = ?, title_name_en = ?,
                description = ?, description_en = ?, enabled = ?,
                translation_status = ?,
                version = version + 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND version = ?
            """,
            (
                model.strip(),
                model.strip(),
                product_name_zh.strip(),
                product_name_en.strip(),
                overview_zh.strip(),
                overview_en.strip(),
                int(enabled),
                translation_status,
                product_id,
                version,
            ),
        )

        if colors is not None:
            submitted_color_ids = []
            normalized_colors = []
            for color_index, color in enumerate(colors):
                color_id = str(color.get("id") or "color-{}".format(uuid.uuid4().hex)).strip()
                if not color_id or color_id in submitted_color_ids:
                    raise CatalogValidationError("PRODUCT_COLOR_DUPLICATE", "colors")
                name_zh = str(color.get("name_zh") or "").strip()
                name_en = str(color.get("name_en") or "").strip()
                if not name_zh or not name_en:
                    raise CatalogValidationError("CATALOG_TRANSLATION_REQUIRED", "colors")
                display_color = str(color.get("display_color") or "#374151").strip()
                if not DISPLAY_COLOR.fullmatch(display_color):
                    raise CatalogValidationError("PRODUCT_COLOR_INVALID", "colors")
                translation_status = str(color.get("translation_status") or "machine_draft")
                if translation_status not in TRANSLATION_STATUSES:
                    raise CatalogValidationError("CATALOG_TRANSLATION_STATUS_INVALID", "colors")
                width = color.get("image_width")
                height = color.get("image_height")
                if width is not None and int(width) <= 0:
                    raise CatalogValidationError("PRODUCT_IMAGE_SIZE_INVALID", "colors")
                if height is not None and int(height) <= 0:
                    raise CatalogValidationError("PRODUCT_IMAGE_SIZE_INVALID", "colors")
                if not validate_media_reference(color.get("image_path")):
                    raise CatalogValidationError("CATALOG_MEDIA_NOT_FOUND", "colors")
                normalized_colors.append(
                    {
                        "id": color_id,
                        "name_zh": name_zh,
                        "name_en": name_en,
                        "display_color": display_color.lower(),
                        "image_path": str(color.get("image_path") or "").strip() or None,
                        "image_width": int(width) if width is not None else None,
                        "image_height": int(height) if height is not None else None,
                        "is_default": bool(color.get("is_default", False)),
                        "enabled": bool(color.get("enabled", True)),
                        "sort_order": int(color.get("sort_order", color_index)),
                        "translation_status": translation_status,
                    }
                )
                submitted_color_ids.append(color_id)
            enabled_colors = [color for color in normalized_colors if color["enabled"]]
            if not enabled_colors:
                raise CatalogValidationError("PRODUCT_COLOR_REQUIRED", "colors")
            enabled_defaults = [color for color in enabled_colors if color["is_default"]]
            if len(enabled_defaults) != 1:
                raise CatalogValidationError("PRODUCT_COLOR_DEFAULT_INVALID", "colors")
            if any(color["is_default"] and not color["enabled"] for color in normalized_colors):
                raise CatalogValidationError("PRODUCT_COLOR_DEFAULT_INVALID", "colors")

            placeholders = ",".join("?" for _ in submitted_color_ids)
            db.execute(
                "DELETE FROM product_colors WHERE product_id = ? AND code NOT IN ({})".format(placeholders),
                [product_id] + submitted_color_ids,
            )
            for color in normalized_colors:
                db.execute(
                    """
                    INSERT INTO product_colors
                        (product_id, code, label, label_en, image_path,
                         display_color, image_width, image_height, is_default,
                         sort_order, enabled, version, translation_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                    ON CONFLICT(product_id, code) DO UPDATE SET
                        label = excluded.label,
                        label_en = excluded.label_en,
                        image_path = excluded.image_path,
                        display_color = excluded.display_color,
                        image_width = excluded.image_width,
                        image_height = excluded.image_height,
                        is_default = excluded.is_default,
                        sort_order = excluded.sort_order,
                        enabled = excluded.enabled,
                        version = product_colors.version + 1,
                        translation_status = excluded.translation_status
                    """,
                    (
                        product_id,
                        color["id"],
                        color["name_zh"],
                        color["name_en"],
                        color["image_path"],
                        color["display_color"],
                        color["image_width"],
                        color["image_height"],
                        int(color["is_default"]),
                        color["sort_order"],
                        int(color["enabled"]),
                        color["translation_status"],
                    ),
                )

        if specifications is not None:
            normalized_specifications = []
            seen_specification_ids = set()
            for spec_index, spec in enumerate(specifications):
                values = {
                    "label": str(spec.get("label") or "").strip(),
                    "label_en": str(spec.get("label_en") or "").strip(),
                    "value": str(spec.get("value") or "").strip(),
                    "value_en": str(spec.get("value_en") or "").strip(),
                }
                if not any(values.values()):
                    continue
                if not all(values.values()):
                    raise CatalogValidationError("PRODUCT_SPECIFICATION_INCOMPLETE", "specifications")
                spec_id = str(spec.get("id") or uuid.uuid4().hex).strip()
                if not spec_id or spec_id in seen_specification_ids:
                    raise CatalogValidationError("PRODUCT_SPECIFICATION_DUPLICATE", "specifications")
                owner = db.execute(
                    "SELECT product_id FROM product_specifications WHERE id = ?",
                    (spec_id,),
                ).fetchone()
                if owner is not None and owner["product_id"] != product_id:
                    raise CatalogValidationError("PRODUCT_SPECIFICATION_INVALID", "specifications")
                seen_specification_ids.add(spec_id)
                normalized_specifications.append(
                    {
                        "id": spec_id,
                        **values,
                        "sort_order": int(spec.get("sort_order", spec_index)),
                    }
                )
            db.execute("DELETE FROM product_specifications WHERE product_id = ?", (product_id,))
            for spec in normalized_specifications:
                db.execute(
                    """
                    INSERT INTO product_specifications
                        (id, product_id, label, label_en, value, value_en, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        spec["id"],
                        product_id,
                        spec["label"],
                        spec["label_en"],
                        spec["value"],
                        spec["value_en"],
                        spec["sort_order"],
                    ),
                )

        existing_group_ids = {
            row[0]
            for row in db.execute(
                "SELECT id FROM product_base_option_groups WHERE product_id = ?",
                (product_id,),
            ).fetchall()
        }
        submitted_group_ids = set()
        submitted_options: Dict[str, str] = {}
        option_types_by_id: Dict[str, str] = {}
        enabled_option_ids = set()

        for group_index, group in enumerate(groups):
            option_type = group["option_type"]
            group_enabled = bool(group.get("enabled", True))
            group_id = str(group.get("id") or "base-{}-{}".format(product_id, option_type))
            group_owner = db.execute(
                "SELECT product_id FROM product_base_option_groups WHERE id = ?",
                (group_id,),
            ).fetchone()
            if group_owner is not None and group_owner["product_id"] != product_id:
                raise CatalogValidationError("BASE_OPTION_GROUP_INVALID", "base_option_groups")
            submitted_group_ids.add(group_id)
            db.execute(
                """
                INSERT INTO product_base_option_groups
                    (id, product_id, option_type, required, single_select,
                     sort_order, enabled, version, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(product_id, option_type) DO UPDATE SET
                    required = excluded.required,
                    single_select = 1,
                    sort_order = excluded.sort_order,
                    enabled = excluded.enabled,
                    version = product_base_option_groups.version + 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    group_id,
                    product_id,
                    option_type,
                    int(bool(group.get("required", True))),
                    int(group.get("sort_order", group_index)),
                    int(group_enabled),
                ),
            )
            actual_group = db.execute(
                "SELECT id FROM product_base_option_groups WHERE product_id = ? AND option_type = ?",
                (product_id, option_type),
            ).fetchone()[0]
            submitted_group_ids.add(actual_group)
            options = list(group.get("options") or [])
            if group_enabled and not any(bool(item.get("enabled", True)) for item in options):
                raise CatalogValidationError(
                    "BASE_OPTION_REQUIRED",
                    "base_option_groups.{}.options".format(option_type),
                )
            submitted_in_group = set()
            for option_index, option in enumerate(options):
                option_id = str(option.get("id") or uuid.uuid4().hex)
                if option_id in submitted_options:
                    raise CatalogValidationError("BASE_OPTION_DUPLICATE", "base_option_groups")
                option_owner = db.execute(
                    """
                    SELECT g.product_id
                    FROM product_base_options o
                    JOIN product_base_option_groups g ON g.id = o.group_id
                    WHERE o.id = ?
                    """,
                    (option_id,),
                ).fetchone()
                if option_owner is not None and option_owner["product_id"] != product_id:
                    raise CatalogValidationError("BASE_OPTION_NOT_AVAILABLE", "base_option_groups")
                name_zh = str(option.get("name_zh") or "").strip()
                name_en = str(option.get("name_en") or "").strip()
                if not name_zh or not name_en:
                    raise CatalogValidationError("CATALOG_TRANSLATION_REQUIRED", "base_option_groups")
                cny = int(option.get("price_cny_minor") or 0)
                usd = int(option.get("price_usd_minor") or 0)
                if cny < 0 or usd < 0:
                    raise CatalogValidationError("CATALOG_PRICE_INVALID", "base_option_groups")
                is_free = bool(option.get("is_free", False))
                if is_free and (cny or usd):
                    raise CatalogValidationError("CATALOG_FREE_PRICE_CONFLICT", "base_option_groups")
                if option_type in ("motor", "channel") and (cny or usd or is_free):
                    raise CatalogValidationError("BASE_OPTION_PRICE_ROLE_INVALID", "base_option_groups")
                translation_status = str(option.get("translation_status") or "machine_draft")
                if translation_status not in ("machine_draft", "reviewed"):
                    raise CatalogValidationError("CATALOG_TRANSLATION_STATUS_INVALID", "base_option_groups")
                option_enabled = bool(option.get("enabled", True))
                db.execute(
                    """
                    INSERT INTO product_base_options
                        (id, group_id, name_zh, name_en, price_cny_minor,
                         price_usd_minor, price_confirmed, is_free, sort_order,
                         enabled, version, translation_status, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        group_id = excluded.group_id,
                        name_zh = excluded.name_zh,
                        name_en = excluded.name_en,
                        price_cny_minor = excluded.price_cny_minor,
                        price_usd_minor = excluded.price_usd_minor,
                        price_confirmed = excluded.price_confirmed,
                        is_free = excluded.is_free,
                        sort_order = excluded.sort_order,
                        enabled = excluded.enabled,
                        version = product_base_options.version + 1,
                        translation_status = excluded.translation_status,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        option_id,
                        actual_group,
                        name_zh,
                        name_en,
                        cny,
                        usd,
                        int(bool(option.get("price_confirmed", False))),
                        int(is_free),
                        int(option.get("sort_order", option_index)),
                        int(option_enabled),
                        translation_status,
                    ),
                )
                submitted_in_group.add(option_id)
                submitted_options[option_id] = actual_group
                option_types_by_id[option_id] = option_type
                if group_enabled and option_enabled:
                    enabled_option_ids.add(option_id)
            if submitted_in_group:
                placeholders = ",".join("?" for _ in submitted_in_group)
                db.execute(
                    """
                    UPDATE product_base_options SET enabled = 0
                    WHERE group_id = ? AND id NOT IN ({})
                    """.format(placeholders),
                    [actual_group] + list(submitted_in_group),
                )

        stale_groups = existing_group_ids - submitted_group_ids
        if stale_groups:
            placeholders = ",".join("?" for _ in stale_groups)
            db.execute(
                "UPDATE product_base_option_groups SET enabled = 0 WHERE id IN ({})".format(placeholders),
                list(stale_groups),
            )

        active_motor_ids = {
            option_id for option_id, option_type in option_types_by_id.items()
            if option_type == "motor" and option_id in enabled_option_ids
        }
        active_channel_ids = {
            option_id for option_id, option_type in option_types_by_id.items()
            if option_type == "channel" and option_id in enabled_option_ids
        }
        seen_combinations = set()
        submitted_variant_ids = set()
        for variant in variants:
            variant_id = str(variant.get("id") or uuid.uuid4().hex)
            motor_id = variant.get("motor_option_id") or None
            channel_id = variant.get("channel_option_id") or None
            if motor_id not in active_motor_ids and motor_id is not None:
                raise CatalogValidationError("PRICE_VARIANT_OPTION_INVALID", "price_variants")
            if channel_id not in active_channel_ids and channel_id is not None:
                raise CatalogValidationError("PRICE_VARIANT_OPTION_INVALID", "price_variants")
            if motor_id is None and channel_id is None:
                raise CatalogValidationError("PRICE_VARIANT_OPTION_REQUIRED", "price_variants")
            combination = (motor_id, channel_id)
            if combination in seen_combinations:
                raise CatalogValidationError("PRICE_VARIANT_DUPLICATE", "price_variants")
            seen_combinations.add(combination)
            existing_combination = db.execute(
                """
                SELECT id FROM product_price_variants
                WHERE product_id = ?
                  AND ((motor_option_id = ?) OR (motor_option_id IS NULL AND ? IS NULL))
                  AND ((channel_option_id = ?) OR (channel_option_id IS NULL AND ? IS NULL))
                """,
                (product_id, motor_id, motor_id, channel_id, channel_id),
            ).fetchone()
            if existing_combination is not None and existing_combination["id"] != variant_id:
                raise CatalogValidationError("PRICE_VARIANT_DUPLICATE", "price_variants")
            variant_owner = db.execute(
                "SELECT product_id FROM product_price_variants WHERE id = ?",
                (variant_id,),
            ).fetchone()
            if variant_owner is not None and variant_owner["product_id"] != product_id:
                raise CatalogValidationError("PRICE_VARIANT_OPTION_INVALID", "price_variants")
            cny = int(variant.get("price_cny_minor") or 0)
            usd = int(variant.get("price_usd_minor") or 0)
            if cny < 0 or usd < 0:
                raise CatalogValidationError("CATALOG_PRICE_INVALID", "price_variants")
            db.execute(
                """
                INSERT INTO product_price_variants
                    (id, product_id, motor_option_id, channel_option_id,
                     price_cny_minor, price_usd_minor, price_confirmed,
                     enabled, version, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    motor_option_id = excluded.motor_option_id,
                    channel_option_id = excluded.channel_option_id,
                    price_cny_minor = excluded.price_cny_minor,
                    price_usd_minor = excluded.price_usd_minor,
                    price_confirmed = excluded.price_confirmed,
                    enabled = excluded.enabled,
                    version = product_price_variants.version + 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    variant_id,
                    product_id,
                    motor_id,
                    channel_id,
                    cny,
                    usd,
                    int(bool(variant.get("price_confirmed", False))),
                    int(bool(variant.get("enabled", True))),
                ),
            )
            submitted_variant_ids.add(variant_id)

        if not variants:
            raise CatalogValidationError("PRICE_VARIANT_REQUIRED", "price_variants")
        enabled_combinations = {
            (variant.get("motor_option_id") or None, variant.get("channel_option_id") or None)
            for variant in variants if variant.get("enabled", True)
        }
        # A model may expose both motor and channel selectors while only one of
        # them determines its base price. The submitted enabled variants define
        # which dimensions participate in pricing.
        prices_by_motor = any(motor_id is not None for motor_id, _ in enabled_combinations)
        prices_by_channel = any(channel_id is not None for _, channel_id in enabled_combinations)
        if prices_by_motor and prices_by_channel:
            expected_combinations = {
                (motor_id, channel_id)
                for motor_id in active_motor_ids
                for channel_id in active_channel_ids
            }
        elif prices_by_motor:
            expected_combinations = {(motor_id, None) for motor_id in active_motor_ids}
        elif prices_by_channel:
            expected_combinations = {(None, channel_id) for channel_id in active_channel_ids}
        else:
            expected_combinations = set()
        if expected_combinations != enabled_combinations:
            raise CatalogValidationError("PRICE_VARIANT_COVERAGE_INVALID", "price_variants")
        if submitted_variant_ids:
            placeholders = ",".join("?" for _ in submitted_variant_ids)
            db.execute(
                """
                UPDATE product_price_variants SET enabled = 0
                WHERE product_id = ? AND id NOT IN ({})
                """.format(placeholders),
                [product_id] + list(submitted_variant_ids),
            )

        db.execute("UPDATE product_options SET enabled = 0 WHERE product_id = ?", (product_id,))
        for sort_order, item in enumerate(validated_options):
            mapping_id = "{}-{}-{}".format(product_id.upper(), item["category_id"].upper(), item["code"])
            override = optional_config_overrides.get(item["id"])
            if override is None:
                existing_override = db.execute(
                    """
                    SELECT description_override, description_override_en
                    FROM product_options WHERE product_id = ? AND option_id = ?
                    """,
                    (product_id, item["id"]),
                ).fetchone()
                override = dict(existing_override) if existing_override is not None else {}
            note_zh = str(override.get("description_override") or "").strip() or None
            note_en = str(override.get("description_override_en") or "").strip() or None
            db.execute(
                """
                INSERT INTO product_options
                    (product_id, option_id, mapping_id, description_override,
                     description_override_en, image_override, price_override,
                     enabled, sort_order)
                VALUES (?, ?, ?, ?, ?, NULL, NULL, 1, ?)
                ON CONFLICT(product_id, option_id) DO UPDATE SET
                    mapping_id = excluded.mapping_id,
                    description_override = excluded.description_override,
                    description_override_en = excluded.description_override_en,
                    image_override = NULL,
                    price_override = NULL,
                    enabled = 1,
                    sort_order = excluded.sort_order
                """,
                (product_id, item["id"], mapping_id, note_zh, note_en, sort_order),
            )

    result = get_product_editor(product_id)
    if result is None:
        raise CatalogValidationError("CATALOG_PRODUCT_NOT_FOUND", "product_id")
    return result
