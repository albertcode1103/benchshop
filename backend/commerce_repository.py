"""Unified cart operations for devices, service tools, and accessories."""

import json
import secrets
import uuid
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .catalog_cart_repository import _catalog_snapshot, get_saved_catalog_item
from .catalog_refactor_repository import CatalogValidationError
from .config_repository import build_snapshot, get_saved_config, get_share as get_legacy_share
from .repository import get_public_product_snapshot
from .database import get_connection
from .security import to_iso, utc_now


ITEM_TYPES = ("device_config", "tool", "accessory")
SHARE_DAYS = 90
ITEM_TYPE_ORDER = {"device_config": 0, "tool": 1, "accessory": 2}
# Cart-level sharing and export intentionally act on the entire cart.  Keep the
# device ceiling aligned with the total cart-item ceiling so a valid cart never
# fails merely because it contains more than 20 saved device configurations.
MAX_DEVICE_CONFIGS_PER_BATCH = 100
MAX_CART_ITEMS_PER_BATCH = 100


def _snapshot_selections(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    selections: Dict[str, Any] = {}
    for category in snapshot.get("categories") or []:
        option_ids = [option.get("id") for option in category.get("options") or [] if option.get("id")]
        if option_ids:
            selections[category.get("id")] = option_ids if category.get("multiple") else option_ids[0]
    return selections


def _device_import_candidate(snapshot: Dict[str, Any], language: str) -> Dict[str, Any]:
    product = snapshot.get("product") or {}
    product_id = str(product.get("id") or "")
    color_code = str((snapshot.get("color") or {}).get("code") or "")
    missing: List[str] = []
    current = get_public_product_snapshot(product_id, language) if product_id else None
    if current is None:
        missing.append(str(product.get("name") or product.get("title_name") or product_id or "Unknown product"))
    else:
        current_colors = {str(color.get("code")) for color in current.get("colors") or []}
        if color_code not in current_colors:
            missing.append(str((snapshot.get("color") or {}).get("label") or color_code or "Color"))
        current_option_ids = {
            str(option.get("id"))
            for group in (current.get("base_option_groups") or []) + (current.get("optional_categories") or [])
            for option in group.get("options") or []
            if option.get("id")
        }
        for category in snapshot.get("categories") or []:
            for option in category.get("options") or []:
                if option.get("id") and str(option["id"]) not in current_option_ids:
                    missing.append(str(option.get("code") or option.get("name") or option["id"]))
    if missing:
        return {"available": False, "missing": list(dict.fromkeys(missing))}
    try:
        rebuilt = build_snapshot(product_id, color_code, _snapshot_selections(snapshot), language)
    except ValueError:
        return {"available": False, "missing": ["Selection rules changed" if language == "en" else "选配规则已变更"]}
    return {"available": True, "missing": [], "snapshot": rebuilt, "product_id": product_id}


def _share_item_candidate(item: Dict[str, Any], language: str) -> Dict[str, Any]:
    item_type = str(item.get("item_type") or "device_config")
    snapshot = item.get("snapshot") or {}
    if item_type == "device_config":
        return _device_import_candidate(snapshot, language)
    option_id = str(snapshot.get("option_id") or "")
    try:
        live_snapshot = _catalog_snapshot(option_id)
    except CatalogValidationError:
        label = snapshot.get("code") or snapshot.get("name") or item.get("display_name") or option_id or "Catalog item"
        return {"available": False, "missing": [str(label)]}
    expected_type = "tools" if item_type == "tool" else "accessories"
    if live_snapshot.get("catalog_type") != expected_type:
        return {"available": False, "missing": [str(snapshot.get("code") or option_id)]}
    return {"available": True, "missing": [], "option_id": option_id, "snapshot": live_snapshot}


def customer_share_preview(code: str, language: str = "zh", increment_view: bool = True) -> Optional[Dict[str, Any]]:
    selected_language = "en" if language == "en" else "zh"
    share = get_any_share(code, selected_language, increment_view)
    if share is None:
        return None
    items = []
    for index, item in enumerate(share.get("items") or []):
        candidate = _share_item_candidate(item, selected_language)
        items.append(
            {
                "key": "{}:{}".format(item.get("item_type", "device_config"), index),
                "item_type": item.get("item_type", "device_config"),
                "quantity": int(item.get("quantity") or 1),
                "display_name": item.get("display_name") or "",
                "snapshot": item.get("snapshot") or {},
                "available": bool(candidate.get("available")),
                "missing": candidate.get("missing") or [],
            }
        )
    return {
        "code": share.get("code") or code,
        "title": share.get("title") or ("Configuration" if selected_language == "en" else "设备配置"),
        "expires_at": share.get("expires_at"),
        "item_count": len(items),
        "available_count": sum(1 for item in items if item["available"]),
        "items": items,
    }


def import_share_to_cart(code: str, user_id: str, idempotency_key: str, language: str = "zh") -> Dict[str, Any]:
    selected_language = "en" if language == "en" else "zh"
    share = get_any_share(code, selected_language, increment_view=False)
    if share is None:
        raise CatalogValidationError("SHARE_NOT_FOUND", "code")
    prepared = []
    skipped = []
    for index, item in enumerate(share.get("items") or []):
        candidate = _share_item_candidate(item, selected_language)
        if candidate.get("available"):
            prepared.append((index, item, candidate))
        else:
            skipped.append(
                {
                    "item_type": item.get("item_type", "device_config"),
                    "display_name": item.get("display_name") or "",
                    "missing": candidate.get("missing") or [],
                }
            )
    if not prepared:
        raise CatalogValidationError("SHARE_NO_AVAILABLE_ITEMS", "code")

    with get_connection() as db:
        previous = db.execute(
            "SELECT result_json FROM share_imports WHERE user_id = ? AND idempotency_key = ?",
            (user_id, idempotency_key),
        ).fetchone()
        if previous is not None:
            result = json.loads(previous["result_json"])
            result["replayed"] = True
            return result

        imported = []
        warnings = []
        for _, item, candidate in prepared:
            item_type = str(item.get("item_type") or "device_config")
            if item_type == "device_config":
                config_id = uuid.uuid4().hex
                snapshot = candidate["snapshot"]
                name = str(item.get("display_name") or (snapshot.get("product") or {}).get("name") or "Configuration")
                db.execute(
                    "INSERT INTO saved_configs (id, user_id, name, product_id, snapshot_json) VALUES (?, ?, ?, ?, ?)",
                    (config_id, user_id, name, candidate["product_id"], json.dumps(snapshot, ensure_ascii=False)),
                )
                imported.append({"item_type": item_type, "id": config_id, "quantity": 1})
                continue

            option_id = candidate["option_id"]
            rows = db.execute(
                "SELECT id, quantity FROM saved_catalog_items WHERE user_id = ? AND option_id = ? AND archived_at IS NULL ORDER BY created_at, id",
                (user_id, option_id),
            ).fetchall()
            requested_quantity = int(item.get("quantity") or 1)
            existing_quantity = sum(int(row["quantity"] or 0) for row in rows)
            target_quantity = min(999, existing_quantity + requested_quantity)
            if target_quantity < existing_quantity + requested_quantity:
                warnings.append({"item_type": item_type, "display_name": item.get("display_name") or "", "code": "QUANTITY_LIMIT"})
            if rows:
                item_id = rows[0]["id"]
                db.execute(
                    "UPDATE saved_catalog_items SET quantity = ?, version = version + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (target_quantity, item_id),
                )
                for duplicate in rows[1:]:
                    db.execute(
                        "UPDATE saved_catalog_items SET archived_at = CURRENT_TIMESTAMP, version = version + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (duplicate["id"],),
                    )
            else:
                item_id = uuid.uuid4().hex
                live_snapshot = candidate["snapshot"]
                db.execute(
                    "INSERT INTO saved_catalog_items (id, user_id, option_id, catalog_type, quantity, snapshot_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (item_id, user_id, option_id, live_snapshot["catalog_type"], target_quantity, json.dumps(live_snapshot, ensure_ascii=False)),
                )
            imported.append({"item_type": item_type, "id": item_id, "quantity": target_quantity})

        result = {
            "share_code": code,
            "imported_count": len(imported),
            "skipped_count": len(skipped),
            "items": imported,
            "skipped": skipped,
            "warnings": warnings,
            "replayed": False,
        }
        db.execute(
            "INSERT INTO share_imports (id, share_id, user_id, idempotency_key, result_json) VALUES (?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, str(share.get("id") or code), user_id, idempotency_key, json.dumps(result, ensure_ascii=False)),
        )
    return result


def _normalize_refs(items: Sequence[Dict[str, Any]]) -> List[Tuple[str, str]]:
    normalized: List[Tuple[str, str]] = []
    seen = set()
    for item in items:
        item_type = str(item.get("item_type") or "")
        source_id = str(item.get("id") or item.get("source_id") or "")
        if item_type not in ITEM_TYPES or not source_id:
            raise CatalogValidationError("CART_ITEM_REFERENCE_INVALID", "items")
        key = (item_type, source_id)
        if key not in seen:
            seen.add(key)
            normalized.append(key)
    if not normalized:
        raise CatalogValidationError("BATCH_SELECTION_EMPTY", "items")
    if sum(1 for item_type, _ in normalized if item_type == "device_config") > MAX_DEVICE_CONFIGS_PER_BATCH:
        raise CatalogValidationError("BATCH_SELECTION_LIMIT", "items")
    if len(normalized) > MAX_CART_ITEMS_PER_BATCH:
        raise CatalogValidationError("CART_BATCH_SELECTION_LIMIT", "items")
    return normalized


def _catalog_document(saved: Dict[str, Any], item_type: str) -> Dict[str, Any]:
    snapshot = saved.get("snapshot") or {}
    return {
        "schema_version": 1,
        "item_type": item_type,
        "catalog_type": saved.get("catalog_type"),
        "source_id": saved.get("id"),
        "option_id": saved.get("option_id"),
        "code": saved.get("code") or snapshot.get("code") or "",
        "name": saved.get("name") or "",
        "description": saved.get("description") or "",
        "note": saved.get("note") or "",
        "image_path": saved.get("image_path") or snapshot.get("image_path"),
        "image_width": snapshot.get("image_width"),
        "image_height": snapshot.get("image_height"),
        "price_cny": int(saved.get("price_cny") or snapshot.get("price_cny") or 0),
        "price_usd": int(saved.get("price_usd") or snapshot.get("price_usd") or 0),
        "quantity": int(saved.get("quantity") or 1),
        "category_sort_order": int(saved.get("catalog_category_sort_order", 2147483647)),
        "sort_order": int(saved.get("catalog_sort_order", 2147483647)),
    }


def _canonical_cart_order(item: Dict[str, Any]) -> Tuple[Any, ...]:
    """Devices follow cart creation time; catalog items follow the managed catalog order."""
    item_type = str(item.get("item_type") or "")
    rank = ITEM_TYPE_ORDER.get(item_type, 99)
    if item_type == "device_config":
        return (rank, str(item.get("created_at") or ""), str(item.get("source_id") or ""))
    return (
        rank,
        int(item.get("catalog_category_sort_order", 2147483647)),
        int(item.get("catalog_sort_order", 2147483647)),
        str(item.get("display_name") or ""),
        str(item.get("source_id") or ""),
    )


def _load_share_item(item_type: str, source_id: str, user_id: str) -> Dict[str, Any]:
    if item_type == "device_config":
        zh = get_saved_config(source_id, user_id, "zh")
        en = get_saved_config(source_id, user_id, "en")
        if zh is None or en is None:
            raise CatalogValidationError("CONFIG_ACCESS_DENIED", "items")
        return {
            "item_type": item_type,
            "source_id": source_id,
            "created_at": zh.get("created_at") or "",
            "catalog_category_sort_order": 0,
            "catalog_sort_order": 0,
            "quantity": 1,
            "display_name": zh.get("name") or (zh.get("snapshot") or {}).get("product", {}).get("name") or "",
            "product_model": (zh.get("snapshot") or {}).get("product", {}).get("name") or "",
            "payload": {"zh": zh["snapshot"], "en": en["snapshot"]},
        }

    expected_catalog_type = "tools" if item_type == "tool" else "accessories"
    zh_saved = get_saved_catalog_item(source_id, user_id, "zh")
    en_saved = get_saved_catalog_item(source_id, user_id, "en")
    if zh_saved is None or en_saved is None or zh_saved.get("catalog_type") != expected_catalog_type:
        raise CatalogValidationError("CONFIG_ACCESS_DENIED", "items")
    return {
        "item_type": item_type,
        "source_id": source_id,
        "created_at": zh_saved.get("created_at") or "",
        "catalog_category_sort_order": int(zh_saved.get("catalog_category_sort_order", 2147483647)),
        "catalog_sort_order": int(zh_saved.get("catalog_sort_order", 2147483647)),
        "quantity": int(zh_saved.get("quantity") or 1),
        "display_name": zh_saved.get("name") or zh_saved.get("code") or "",
        "product_model": "",
        "payload": {
            "zh": _catalog_document(zh_saved, item_type),
            "en": _catalog_document(en_saved, item_type),
        },
    }


def create_commerce_share(items: Sequence[Dict[str, Any]], user_id: str, lang: str = "zh") -> Dict[str, Any]:
    refs = _normalize_refs(items)
    loaded = sorted(
        (_load_share_item(item_type, source_id, user_id) for item_type, source_id in refs),
        key=_canonical_cart_order,
    )
    language = "en" if lang == "en" else "zh"
    share_id = uuid.uuid4().hex
    expires_at = to_iso(utc_now() + timedelta(days=SHARE_DAYS))
    models = list(dict.fromkeys(item["product_model"] for item in loaded if item["product_model"]))
    primary_config_id = next((item["source_id"] for item in loaded if item["item_type"] == "device_config"), None)
    with get_connection() as db:
        user = db.execute("SELECT display_name, email, phone FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise CatalogValidationError("CONFIG_ACCESS_DENIED", "items")
        code = None
        for _ in range(30):
            candidate = "{:06d}".format(secrets.randbelow(1000000))
            collision = db.execute(
                "SELECT 1 FROM config_shares WHERE code = ? UNION ALL SELECT 1 FROM commerce_shares WHERE code = ? LIMIT 1",
                (candidate, candidate),
            ).fetchone()
            if collision is None:
                code = candidate
                break
        if code is None:
            raise RuntimeError("Unable to allocate a share code")
        db.execute(
            """
            INSERT INTO commerce_shares
                (id, code, created_by, expires_at, title, language,
                 customer_name, customer_email, item_count, product_summary,
                 primary_config_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                share_id,
                code,
                user_id,
                expires_at,
                "Configuration" if language == "en" else "设备配置",
                language,
                user["display_name"] or "",
                user["email"] or user["phone"] or "",
                len(loaded),
                ", ".join(models),
                primary_config_id,
            ),
        )
        for index, item in enumerate(loaded):
            db.execute(
                """
                INSERT INTO commerce_share_items
                    (id, share_id, item_type, source_id, sort_order,
                     quantity, display_name, snapshot_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    share_id,
                    item["item_type"],
                    item["source_id"],
                    index,
                    item["quantity"],
                    item["display_name"],
                    json.dumps(item["payload"], ensure_ascii=False),
                ),
            )
        device_ids = [item["source_id"] for item in loaded if item["item_type"] == "device_config"]
        if device_ids:
            placeholders = ",".join("?" for _ in device_ids)
            db.execute(
                "UPDATE saved_configs SET status = 'shared', updated_at = CURRENT_TIMESTAMP WHERE id IN ({})".format(placeholders),
                device_ids,
            )
    return {
        "id": share_id,
        "code": code,
        "config_id": primary_config_id,
        "item_count": len(loaded),
        "expires_at": expires_at,
        "document_version": 2,
    }


def load_cart_documents(items: Sequence[Dict[str, Any]], user_id: str, lang: str = "zh") -> List[Dict[str, Any]]:
    language = "en" if lang == "en" else "zh"
    refs = _normalize_refs(items)
    loaded = sorted(
        (_load_share_item(item_type, source_id, user_id) for item_type, source_id in refs),
        key=_canonical_cart_order,
    )
    return [
        {
            "item_type": item["item_type"],
            "source_id": item["source_id"],
            "quantity": item["quantity"],
            "display_name": item["display_name"],
            "snapshot": item["payload"].get(language) or {},
        }
        for item in loaded
    ]


def get_commerce_share(code: str, lang: str = "zh", increment_view: bool = True) -> Optional[Dict[str, Any]]:
    language = "en" if lang == "en" else "zh"
    with get_connection() as db:
        row = db.execute(
            """
            SELECT s.*, u.display_name AS sender_name, u.email AS sender_email,
                   u.phone AS sender_phone
            FROM commerce_shares s
            JOIN users u ON u.id = s.created_by
            WHERE s.code = ? AND s.active = 1 AND s.expires_at > ?
            """,
            (code, to_iso(utc_now())),
        ).fetchone()
        if row is None:
            return None
        if increment_view:
            db.execute(
                "UPDATE commerce_shares SET view_count = view_count + 1, last_viewed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (row["id"],),
            )
        rows = db.execute(
            """
            SELECT id, item_type, source_id, sort_order, quantity,
                   display_name, snapshot_json, created_at
            FROM commerce_share_items
            WHERE share_id = ? ORDER BY sort_order, created_at
            """,
            (row["id"],),
        ).fetchall()
    result = dict(row)
    decoded = []
    for source in rows:
        item = dict(source)
        payload = json.loads(item.pop("snapshot_json"))
        item["snapshot"] = payload.get(language) or {}
        if item.get("item_type") == "device_config":
            item["pricing_by_currency"] = {
                "CNY": (payload.get("zh") or {}).get("pricing") or {},
                "USD": (payload.get("en") or {}).get("pricing") or {},
            }
        else:
            item["reference_price"] = {
                "CNY": (payload.get("zh") or {}).get("price_cny", 0),
                "USD": (payload.get("en") or {}).get("price_usd", 0),
            }
        decoded.append(item)
    result["config_id"] = result.pop("primary_config_id")
    result["items"] = decoded
    result["item_count"] = len(decoded)
    first_device = next((item["snapshot"] for item in decoded if item["item_type"] == "device_config"), None)
    result["snapshot"] = first_device or (decoded[0]["snapshot"] if decoded else {})
    result["document_version"] = 2
    return result


def get_any_share(code: str, lang: str = "zh", increment_view: bool = True) -> Optional[Dict[str, Any]]:
    commerce = get_commerce_share(code, lang, increment_view)
    if commerce is not None:
        return commerce
    legacy = get_legacy_share(code, lang, increment_view)
    if legacy is not None:
        legacy["document_version"] = 1
        for item in legacy.get("items") or []:
            item.setdefault("item_type", "device_config")
            item.setdefault("source_id", item.get("config_id"))
            item.setdefault("quantity", 1)
    return legacy


def list_customer_shares(user_id: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    safe_page = max(int(page), 1)
    safe_page_size = min(max(int(page_size), 1), 50)
    offset = (safe_page - 1) * safe_page_size
    union = """
        SELECT id, code, title, item_count, view_count, last_viewed_at,
               expires_at, active, created_at, 1 AS document_version
        FROM config_shares WHERE created_by = ?
        UNION ALL
        SELECT id, code, title, item_count, view_count, last_viewed_at,
               expires_at, active, created_at, 2 AS document_version
        FROM commerce_shares WHERE created_by = ?
    """
    with get_connection() as db:
        total = int(db.execute("SELECT COUNT(*) FROM ({})".format(union), (user_id, user_id)).fetchone()[0])
        rows = db.execute(
            "SELECT * FROM ({}) ORDER BY created_at DESC LIMIT ? OFFSET ?".format(union),
            (user_id, user_id, safe_page_size, offset),
        ).fetchall()
        quote_counts = {
            row["source_share_id"]: int(row["count"])
            for row in db.execute(
                "SELECT source_share_id, COUNT(*) AS count FROM quote_deliveries WHERE recipient_user_id = ? AND status = 'delivered' AND source_share_id IS NOT NULL GROUP BY source_share_id",
                (user_id,),
            ).fetchall()
        }
    now = to_iso(utc_now())
    items = []
    for row in rows:
        item = dict(row)
        item["active"] = bool(item["active"])
        item["status"] = "closed" if not item["active"] else "expired" if item["expires_at"] <= now else "active"
        item["quote_count"] = quote_counts.get(item["id"], 0)
        items.append(item)
    return {"items": items, "total": total, "page": safe_page, "page_size": safe_page_size}


def get_customer_share(share_id: str, user_id: str, language: str = "zh") -> Optional[Dict[str, Any]]:
    selected_language = "en" if language == "en" else "zh"
    with get_connection() as db:
        row = db.execute(
            "SELECT *, 2 AS document_version FROM commerce_shares WHERE id = ? AND created_by = ?",
            (share_id, user_id),
        ).fetchone()
        if row is not None:
            item_rows = db.execute(
                "SELECT id, item_type, source_id, sort_order, quantity, display_name, snapshot_json, created_at FROM commerce_share_items WHERE share_id = ? ORDER BY sort_order, created_at",
                (share_id,),
            ).fetchall()
        else:
            row = db.execute(
                "SELECT *, 1 AS document_version FROM config_shares WHERE id = ? AND created_by = ?",
                (share_id, user_id),
            ).fetchone()
            if row is None:
                return None
            item_rows = db.execute(
                "SELECT id, config_id AS source_id, sort_order, item_type, display_name, snapshot_json, created_at, 1 AS quantity FROM config_share_items WHERE share_id = ? ORDER BY sort_order, created_at",
                (share_id,),
            ).fetchall()
    result = dict(row)
    result["active"] = bool(result["active"])
    now = to_iso(utc_now())
    result["status"] = "closed" if not result["active"] else "expired" if result["expires_at"] <= now else "active"
    decoded_items = []
    for source in item_rows:
        item = dict(source)
        payload = json.loads(item.pop("snapshot_json"))
        item["snapshot"] = payload.get(selected_language) if isinstance(payload, dict) and ("zh" in payload or "en" in payload) else payload
        item["snapshot"] = item["snapshot"] or {}
        item["item_type"] = item.get("item_type") or "device_config"
        candidate = _share_item_candidate(item, selected_language)
        item["available"] = bool(candidate.get("available"))
        item["missing"] = candidate.get("missing") or []
        decoded_items.append(item)
    result["items"] = decoded_items
    result["item_count"] = len(decoded_items)
    result["snapshot"] = decoded_items[0]["snapshot"] if decoded_items else {}
    return result


def archive_cart_items(items: Sequence[Dict[str, Any]], user_id: str) -> int:
    refs = _normalize_refs(items)
    with get_connection() as db:
        for item_type, source_id in refs:
            table = "saved_configs" if item_type == "device_config" else "saved_catalog_items"
            row = db.execute(
                "SELECT 1 FROM {} WHERE id = ? AND user_id = ? AND archived_at IS NULL".format(table),
                (source_id, user_id),
            ).fetchone()
            if row is None:
                raise CatalogValidationError("CONFIG_ACCESS_DENIED", "items")
        for item_type, source_id in refs:
            if item_type == "device_config":
                db.execute(
                    "UPDATE saved_configs SET archived_at = CURRENT_TIMESTAMP, status = 'closed', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                    (source_id, user_id),
                )
            else:
                db.execute(
                    "UPDATE saved_catalog_items SET archived_at = CURRENT_TIMESTAMP, version = version + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                    (source_id, user_id),
                )
    return len(refs)


def deactivate_any_share(share_id: str) -> bool:
    with get_connection() as db:
        cursor = db.execute("UPDATE commerce_shares SET active = 0 WHERE id = ?", (share_id,))
        if cursor.rowcount:
            return True
        cursor = db.execute("UPDATE config_shares SET active = 0 WHERE id = ?", (share_id,))
    return cursor.rowcount > 0


def set_any_share_active(share_id: str, active: bool) -> bool:
    """Update legacy or commerce share state without changing its snapshot."""
    enabled = 1 if active else 0
    with get_connection() as db:
        cursor = db.execute("UPDATE commerce_shares SET active = ? WHERE id = ?", (enabled, share_id))
        if cursor.rowcount:
            return True
        cursor = db.execute("UPDATE config_shares SET active = ? WHERE id = ?", (enabled, share_id))
    return cursor.rowcount > 0


def search_all_shares(
    page: int = 1,
    page_size: int = 20,
    query: str = "",
    share_status: str = "all",
    product_id: str = "",
    created_from: str = "",
    created_to: str = "",
) -> Dict[str, Any]:
    safe_page = max(int(page), 1)
    safe_page_size = min(max(int(page_size), 1), 100)
    now = to_iso(utc_now())
    conditions: List[str] = []
    params: List[Any] = []
    needle = query.strip().lower()
    if needle:
        like = "%{}%".format(needle)
        conditions.append(
            "(LOWER(code) LIKE ? OR LOWER(customer_name) LIKE ? OR LOWER(customer_email) LIKE ? OR LOWER(sender_name) LIKE ? OR LOWER(sender_email) LIKE ? OR LOWER(sender_phone) LIKE ? OR LOWER(product_summary) LIKE ? OR LOWER(COALESCE(search_blob, '')) LIKE ?)"
        )
        params.extend([like] * 8)
    if share_status == "active":
        conditions.append("active = 1 AND expires_at > ?")
        params.append(now)
    elif share_status == "expired":
        conditions.append("active = 1 AND expires_at <= ?")
        params.append(now)
    elif share_status == "closed":
        conditions.append("active = 0")
    if product_id.strip():
        conditions.append("LOWER(product_summary) LIKE ?")
        params.append("%{}%".format(product_id.strip().lower()))
    if created_from.strip():
        conditions.append("date(created_at) >= date(?)")
        params.append(created_from.strip())
    if created_to.strip():
        conditions.append("date(created_at) <= date(?)")
        params.append(created_to.strip())
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    union = """
        SELECT s.id, s.code, s.config_id, s.created_by, s.expires_at, s.active,
               s.view_count, s.last_viewed_at, s.created_at, s.title, s.language,
               s.customer_name, s.customer_email, s.item_count,
               COALESCE(NULLIF((SELECT COUNT(*) FROM config_share_items csi WHERE csi.share_id = s.id), 0), 1) AS device_count,
               0 AS tool_quantity, 0 AS accessory_quantity, c.name,
               c.product_id AS product_id, u.display_name AS sender_name,
               u.email AS sender_email, u.phone AS sender_phone,
               COALESCE((SELECT GROUP_CONCAT(DISTINCT sc.product_id)
                 FROM config_share_items si JOIN saved_configs sc ON sc.id = si.config_id
                 WHERE si.share_id = s.id), c.product_id) AS product_summary,
               1 AS document_version,
               COALESCE((SELECT GROUP_CONCAT(si.display_name || ' ' || si.snapshot_json, ' ')
                 FROM config_share_items si WHERE si.share_id = s.id), '') AS search_blob
        FROM config_shares s
        JOIN saved_configs c ON c.id = s.config_id
        JOIN users u ON u.id = s.created_by
        UNION ALL
        SELECT s.id, s.code, s.primary_config_id AS config_id, s.created_by,
               s.expires_at, s.active, s.view_count, s.last_viewed_at,
               s.created_at, s.title, s.language, s.customer_name,
               s.customer_email, s.item_count,
               COALESCE((SELECT COUNT(*) FROM commerce_share_items csi WHERE csi.share_id = s.id AND csi.item_type = 'device_config'), 0) AS device_count,
               COALESCE((SELECT SUM(CASE WHEN csi.quantity > 0 THEN csi.quantity ELSE 0 END) FROM commerce_share_items csi WHERE csi.share_id = s.id AND csi.item_type = 'tool'), 0) AS tool_quantity,
               COALESCE((SELECT SUM(CASE WHEN csi.quantity > 0 THEN csi.quantity ELSE 0 END) FROM commerce_share_items csi WHERE csi.share_id = s.id AND csi.item_type = 'accessory'), 0) AS accessory_quantity,
               s.title AS name,
               s.product_summary AS product_id, u.display_name AS sender_name,
               u.email AS sender_email, u.phone AS sender_phone,
               s.product_summary, 2 AS document_version,
               COALESCE((SELECT GROUP_CONCAT(si.display_name || ' ' || si.snapshot_json, ' ')
                 FROM commerce_share_items si WHERE si.share_id = s.id), '') AS search_blob
        FROM commerce_shares s JOIN users u ON u.id = s.created_by
    """
    with get_connection() as db:
        total = db.execute("SELECT COUNT(*) FROM ({}) combined {}".format(union, where), params).fetchone()[0]
        rows = db.execute(
            "SELECT * FROM ({}) combined {} ORDER BY created_at DESC LIMIT ? OFFSET ?".format(union, where),
            params + [safe_page_size, (safe_page - 1) * safe_page_size],
        ).fetchall()
        legacy_metrics = db.execute(
            "SELECT COUNT(*), SUM(CASE WHEN active=1 AND expires_at>? THEN 1 ELSE 0 END), COALESCE(SUM(view_count),0) FROM config_shares",
            (now,),
        ).fetchone()
        commerce_metrics = db.execute(
            "SELECT COUNT(*), SUM(CASE WHEN active=1 AND expires_at>? THEN 1 ELSE 0 END), COALESCE(SUM(view_count),0) FROM commerce_shares",
            (now,),
        ).fetchone()
    items = [dict(row) for row in rows]
    for item in items:
        item["active"] = bool(item["active"])
    return {
        "items": items,
        "total": int(total),
        "page": safe_page,
        "page_size": safe_page_size,
        "active_total": int(legacy_metrics[1] or 0) + int(commerce_metrics[1] or 0),
        "view_total": int(legacy_metrics[2] or 0) + int(commerce_metrics[2] or 0),
    }
