"""Unified cart operations for devices, service tools, and accessories."""

import json
import secrets
import uuid
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .catalog_cart_repository import get_saved_catalog_item
from .catalog_refactor_repository import CatalogValidationError
from .config_repository import get_saved_config, get_share as get_legacy_share
from .database import get_connection
from .security import to_iso, utc_now


ITEM_TYPES = ("device_config", "tool", "accessory")
SHARE_DAYS = 90
ITEM_TYPE_ORDER = {"device_config": 0, "tool": 1, "accessory": 2}
MAX_DEVICE_CONFIGS_PER_BATCH = 20
MAX_CART_ITEMS_PER_BATCH = 100


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
               s.customer_name, s.customer_email, s.item_count, c.name,
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
               s.customer_email, s.item_count, s.title AS name,
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
