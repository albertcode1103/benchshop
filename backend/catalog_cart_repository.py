"""Independent cart items for service tools and product accessories."""

import json
import uuid
from typing import Any, Dict, List, Optional

from .catalog_refactor_repository import CatalogValidationError
from .database import get_connection


CATALOG_CART_TYPES = ("tools", "accessories")


def list_public_catalog_items(catalog_type: str, language: str = "zh") -> List[Dict[str, Any]]:
    if catalog_type not in CATALOG_CART_TYPES:
        raise CatalogValidationError("CATALOG_TYPE_INVALID", "catalog_type")
    selected_language = "en" if language == "en" else "zh"
    with get_connection() as db:
        rows = db.execute(
            """
            SELECT o.id, o.category_id, c.catalog_type, c.name AS category_name_zh,
                   c.name_en AS category_name_en, o.code, o.name AS name_zh,
                   o.name_en, o.description AS description_zh,
                   o.description_en, o.notes AS note_zh, o.note_en,
                   o.image_path, o.image_width, o.image_height,
                   o.price AS price_cny, o.price_usd, o.translation_status,
                   o.sort_order
            FROM options o
            JOIN categories c ON c.id = o.category_id
            WHERE c.catalog_type = ? AND c.enabled = 1
              AND o.enabled = 1 AND o.deleted_at IS NULL
            ORDER BY c.sort_order, o.sort_order, o.id
            """,
            (catalog_type,),
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        if selected_language == "en" and not str(item.get("name_en") or "").strip():
            continue
        item["category_name"] = item["category_name_en"] if selected_language == "en" else item["category_name_zh"]
        item["name"] = item["name_en"] if selected_language == "en" else item["name_zh"]
        item["description"] = item["description_en"] if selected_language == "en" else item["description_zh"]
        item["note"] = item["note_en"] if selected_language == "en" else item["note_zh"]
        items.append(item)
    return items


def _catalog_snapshot(option_id: str) -> Dict[str, Any]:
    with get_connection() as db:
        row = db.execute(
            """
            SELECT o.id, o.category_id, c.catalog_type, o.code,
                   o.name AS name_zh, o.name_en,
                   o.description AS description_zh, o.description_en,
                   o.notes AS note_zh, o.note_en, o.image_path,
                   o.image_width, o.image_height, o.price AS price_cny,
                   o.price_usd, o.translation_status,
                   c.sort_order AS category_sort_order, o.sort_order
            FROM options o
            JOIN categories c ON c.id = o.category_id
            WHERE o.id = ? AND c.catalog_type IN ('tools', 'accessories')
              AND c.enabled = 1 AND o.enabled = 1 AND o.deleted_at IS NULL
            """,
            (option_id,),
        ).fetchone()
    if row is None:
        raise CatalogValidationError("CATALOG_ITEM_NOT_AVAILABLE", "option_id")
    return dict(row)


def _decode(row: Any, language: str = "zh") -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    item = dict(row)
    snapshot = json.loads(item.pop("snapshot_json"))
    selected_language = "en" if language == "en" else "zh"
    item["snapshot"] = snapshot
    item["code"] = snapshot.get("code", "")
    item["name"] = snapshot.get("name_en", "") if selected_language == "en" else snapshot.get("name_zh", "")
    item["description"] = snapshot.get("description_en", "") if selected_language == "en" else snapshot.get("description_zh", "")
    item["note"] = snapshot.get("note_en", "") if selected_language == "en" else snapshot.get("note_zh", "")
    item["image_path"] = snapshot.get("image_path")
    item["price_cny"] = int(snapshot.get("price_cny") or 0)
    item["price_usd"] = int(snapshot.get("price_usd") or 0)
    live_sort_order = item.get("catalog_sort_order")
    live_category_sort_order = item.get("catalog_category_sort_order")
    item["catalog_category_sort_order"] = int(
        live_category_sort_order if live_category_sort_order is not None else snapshot.get("category_sort_order", 2147483647)
    )
    item["catalog_sort_order"] = int(
        live_sort_order if live_sort_order is not None else snapshot.get("sort_order", 2147483647)
    )
    return item


def get_saved_catalog_item(item_id: str, user_id: str, language: str = "zh") -> Optional[Dict[str, Any]]:
    with get_connection() as db:
        row = db.execute(
            """
            SELECT sci.id, sci.option_id, sci.catalog_type, sci.quantity,
                   sci.snapshot_json, sci.version, sci.created_at, sci.updated_at,
                   c.sort_order AS catalog_category_sort_order,
                   o.sort_order AS catalog_sort_order
            FROM saved_catalog_items sci
            LEFT JOIN options o ON o.id = sci.option_id
            LEFT JOIN categories c ON c.id = o.category_id
            WHERE sci.id = ? AND sci.user_id = ? AND sci.archived_at IS NULL
            """,
            (item_id, user_id),
        ).fetchone()
    return _decode(row, language)


def list_saved_catalog_items(user_id: str, language: str = "zh") -> List[Dict[str, Any]]:
    with get_connection() as db:
        rows = db.execute(
            """
            SELECT sci.id, sci.option_id, sci.catalog_type, sci.quantity,
                   sci.snapshot_json, sci.version, sci.created_at, sci.updated_at,
                   c.sort_order AS catalog_category_sort_order,
                   o.sort_order AS catalog_sort_order
            FROM saved_catalog_items sci
            LEFT JOIN options o ON o.id = sci.option_id
            LEFT JOIN categories c ON c.id = o.category_id
            WHERE sci.user_id = ? AND sci.archived_at IS NULL
            ORDER BY
                CASE sci.catalog_type WHEN 'tools' THEN 0 WHEN 'accessories' THEN 1 ELSE 2 END,
                COALESCE(c.sort_order, 2147483647), COALESCE(o.sort_order, 2147483647),
                sci.created_at ASC, sci.id ASC
            """,
            (user_id,),
        ).fetchall()
    return [_decode(row, language) for row in rows]  # type: ignore


def save_catalog_item(user_id: str, option_id: str, quantity: int, language: str = "zh") -> Dict[str, Any]:
    if not 1 <= int(quantity) <= 999:
        raise CatalogValidationError("CATALOG_QUANTITY_INVALID", "quantity")
    snapshot = _catalog_snapshot(option_id)
    item_id = uuid.uuid4().hex
    with get_connection() as db:
        db.execute(
            """
            INSERT INTO saved_catalog_items
                (id, user_id, option_id, catalog_type, quantity, snapshot_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                user_id,
                option_id,
                snapshot["catalog_type"],
                int(quantity),
                json.dumps(snapshot, ensure_ascii=False),
            ),
        )
    return get_saved_catalog_item(item_id, user_id, language)  # type: ignore


def update_saved_catalog_item(
    item_id: str,
    user_id: str,
    *,
    version: int,
    quantity: int,
    language: str = "zh",
) -> Dict[str, Any]:
    if not 1 <= int(quantity) <= 999:
        raise CatalogValidationError("CATALOG_QUANTITY_INVALID", "quantity")
    with get_connection() as db:
        current = db.execute(
            """
            SELECT version FROM saved_catalog_items
            WHERE id = ? AND user_id = ? AND archived_at IS NULL
            """,
            (item_id, user_id),
        ).fetchone()
        if current is None:
            raise CatalogValidationError("CATALOG_CART_ITEM_NOT_FOUND", "item_id")
        if int(current["version"]) != int(version):
            raise CatalogValidationError(
                "CATALOG_CART_VERSION_CONFLICT",
                "version",
                {"current_version": int(current["version"])},
            )
        db.execute(
            """
            UPDATE saved_catalog_items
            SET quantity = ?, version = version + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ? AND version = ?
              AND archived_at IS NULL
            """,
            (int(quantity), item_id, user_id, version),
        )
    return get_saved_catalog_item(item_id, user_id, language)  # type: ignore


def archive_saved_catalog_item(item_id: str, user_id: str, *, version: int) -> None:
    with get_connection() as db:
        current = db.execute(
            """
            SELECT version FROM saved_catalog_items
            WHERE id = ? AND user_id = ? AND archived_at IS NULL
            """,
            (item_id, user_id),
        ).fetchone()
        if current is None:
            raise CatalogValidationError("CATALOG_CART_ITEM_NOT_FOUND", "item_id")
        if int(current["version"]) != int(version):
            raise CatalogValidationError(
                "CATALOG_CART_VERSION_CONFLICT",
                "version",
                {"current_version": int(current["version"])},
            )
        db.execute(
            """
            UPDATE saved_catalog_items
            SET archived_at = CURRENT_TIMESTAMP, version = version + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ? AND version = ?
            """,
            (item_id, user_id, version),
        )
