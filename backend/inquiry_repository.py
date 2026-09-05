"""Explicit customer inquiry persistence, separate from configuration shares."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .catalog_refactor_repository import CatalogValidationError
from .commerce_repository import _canonical_cart_order, _load_share_item, _normalize_refs
from .config_repository import build_snapshot
from .database import get_connection


INQUIRY_STATES = {"new", "assigned", "contacted", "quoted", "closed", "cancelled"}


class InquiryError(ValueError):
    """A stable domain-code error that routes can translate for either UI language."""


def _clean_message(value: Any) -> str:
    return str(value or "").strip()[:1000]


def _inquiry_prefix() -> str:
    return "BTI-{}-".format(datetime.now(timezone.utc).strftime("%Y%m%d"))


def _allocate_inquiry_number(db) -> str:
    prefix = _inquiry_prefix()
    row = db.execute(
        "SELECT inquiry_number FROM customer_inquiries WHERE inquiry_number LIKE ? ORDER BY inquiry_number DESC LIMIT 1",
        (prefix + "%",),
    ).fetchone()
    last = 0
    if row and row["inquiry_number"]:
        try:
            last = int(str(row["inquiry_number"])[len(prefix):])
        except ValueError:
            last = 0
    return "{}{:04d}".format(prefix, last + 1)


def _decode_item(row, language: str) -> Dict[str, Any]:
    item = dict(row)
    payload = json.loads(item.pop("snapshot_json"))
    item["snapshot"] = payload.get("en" if language == "en" else "zh") or {}
    return item


def _decode_inquiry(row, item_rows, language: str) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    result = dict(row)
    result["items"] = [_decode_item(item, language) for item in item_rows]
    result["item_count"] = len(result["items"])
    result["document_version"] = 1
    return result


def _load_inquiry(inquiry_id: str, language: str = "zh") -> Optional[Dict[str, Any]]:
    selected_language = "en" if language == "en" else "zh"
    with get_connection() as db:
        row = db.execute(
            """
            SELECT i.*, creator.display_name AS customer_display_name,
                   creator.email AS customer_email_current, creator.phone AS customer_phone_current,
                   assignee.display_name AS assignee_name
            FROM customer_inquiries i
            JOIN users creator ON creator.id = i.created_by
            LEFT JOIN users assignee ON assignee.id = i.assigned_to
            WHERE i.id = ?
            """,
            (inquiry_id,),
        ).fetchone()
        items = db.execute(
            "SELECT id, inquiry_id, item_type, source_id, sort_order, quantity, display_name, snapshot_json, created_at FROM customer_inquiry_items WHERE inquiry_id = ? ORDER BY sort_order, created_at, id",
            (inquiry_id,),
        ).fetchall()
    return _decode_inquiry(row, items, selected_language)


def _insert_inquiry(
    user_id: str,
    source_type: str,
    loaded_items: Sequence[Dict[str, Any]],
    language: str,
    message: str,
    idempotency_key: str,
) -> Dict[str, Any]:
    if source_type not in ("current_device", "cart"):
        raise InquiryError("INQUIRY_CONFIGURATION_INVALID")
    if not loaded_items:
        raise InquiryError("INQUIRY_CART_EMPTY" if source_type == "cart" else "INQUIRY_CONFIGURATION_INVALID")
    if not idempotency_key or not 8 <= len(idempotency_key) <= 80:
        raise InquiryError("INQUIRY_DUPLICATE_REQUEST")
    selected_language = "en" if language == "en" else "zh"
    with get_connection() as db:
        existing = db.execute(
            "SELECT id FROM customer_inquiries WHERE created_by = ? AND idempotency_key = ?",
            (user_id, idempotency_key),
        ).fetchone()
        if existing is not None:
            result = _load_inquiry(existing["id"], selected_language)
            if result is None:
                raise InquiryError("INQUIRY_DUPLICATE_REQUEST")
            result["replayed"] = True
            return result
        customer = db.execute(
            "SELECT display_name, email, phone, phone_country FROM users WHERE id = ? AND enabled = 1 AND deleted_at IS NULL",
            (user_id,),
        ).fetchone()
        if customer is None:
            raise InquiryError("INQUIRY_ACCESS_DENIED")
        inquiry_id = uuid.uuid4().hex
        number = _allocate_inquiry_number(db)
        db.execute(
            """
            INSERT INTO customer_inquiries
                (id, inquiry_number, created_by, source_type, language,
                 customer_name_snapshot, customer_email_snapshot, customer_phone_snapshot,
                 customer_country_snapshot, message, item_count, idempotency_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                inquiry_id, number, user_id, source_type, selected_language,
                customer["display_name"] or "", customer["email"] or "", customer["phone"] or "",
                customer["phone_country"] or "", _clean_message(message), len(loaded_items), idempotency_key,
            ),
        )
        for index, item in enumerate(loaded_items):
            db.execute(
                """
                INSERT INTO customer_inquiry_items
                    (id, inquiry_id, item_type, source_id, sort_order, quantity, display_name, snapshot_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex, inquiry_id, item["item_type"], item.get("source_id"), index,
                    int(item.get("quantity") or 1), item.get("display_name") or "",
                    json.dumps(item["payload"], ensure_ascii=False, allow_nan=False),
                ),
            )
    result = _load_inquiry(inquiry_id, selected_language)
    if result is None:
        raise InquiryError("INQUIRY_NOT_FOUND")
    result["replayed"] = False
    return result


def create_current_device_inquiry(
    user_id: str,
    product_id: str,
    color: str,
    selections: Dict[str, Any],
    language: str,
    message: str,
    idempotency_key: str,
) -> Dict[str, Any]:
    try:
        zh = build_snapshot(product_id, color, selections, "zh")
        en = build_snapshot(product_id, color, selections, "en")
    except (ValueError, TypeError, KeyError):
        raise InquiryError("INQUIRY_CONFIGURATION_INVALID")
    product = zh.get("product") or {}
    document = {
        "item_type": "device_config",
        "source_id": None,
        "quantity": 1,
        "display_name": product.get("name") or product.get("title_name") or "",
        "payload": {"zh": zh, "en": en},
    }
    return _insert_inquiry(user_id, "current_device", [document], language, message, idempotency_key)


def _cart_loaded_items(user_id: str) -> List[Dict[str, Any]]:
    with get_connection() as db:
        device_rows = db.execute(
            "SELECT id FROM saved_configs WHERE user_id = ? AND archived_at IS NULL ORDER BY created_at ASC, id ASC",
            (user_id,),
        ).fetchall()
        catalog_rows = db.execute(
            """
            SELECT id, catalog_type FROM saved_catalog_items
            WHERE user_id = ? AND archived_at IS NULL
            ORDER BY CASE catalog_type WHEN 'tools' THEN 0 WHEN 'accessories' THEN 1 ELSE 2 END,
                     created_at ASC, id ASC
            """,
            (user_id,),
        ).fetchall()
    refs = [{"item_type": "device_config", "id": row["id"]} for row in device_rows]
    refs.extend({"item_type": "tool" if row["catalog_type"] == "tools" else "accessory", "id": row["id"]} for row in catalog_rows)
    try:
        normalized = _normalize_refs(refs)
        loaded = [_load_share_item(item_type, source_id, user_id) for item_type, source_id in normalized]
    except CatalogValidationError:
        raise InquiryError("INQUIRY_CONFIGURATION_INVALID")
    return sorted(loaded, key=_canonical_cart_order)


def create_cart_inquiry(user_id: str, language: str, message: str, idempotency_key: str) -> Dict[str, Any]:
    loaded = _cart_loaded_items(user_id)
    return _insert_inquiry(user_id, "cart", loaded, language, message, idempotency_key)


def list_customer_inquiries(user_id: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    safe_page = max(int(page), 1)
    safe_size = min(max(int(page_size), 1), 50)
    with get_connection() as db:
        total = int(db.execute("SELECT COUNT(*) FROM customer_inquiries WHERE created_by = ?", (user_id,)).fetchone()[0])
        rows = db.execute(
            "SELECT * FROM customer_inquiries WHERE created_by = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, safe_size, (safe_page - 1) * safe_size),
        ).fetchall()
    return {"items": [dict(row) for row in rows], "total": total, "page": safe_page, "page_size": safe_size}


def get_customer_inquiry(inquiry_id: str, user_id: str, language: str = "zh") -> Optional[Dict[str, Any]]:
    inquiry = _load_inquiry(inquiry_id, language)
    return inquiry if inquiry and inquiry["created_by"] == user_id else None


def cancel_customer_inquiry(inquiry_id: str, user_id: str, version: int) -> Optional[Dict[str, Any]]:
    with get_connection() as db:
        row = db.execute("SELECT status, version FROM customer_inquiries WHERE id = ? AND created_by = ?", (inquiry_id, user_id)).fetchone()
        if row is None:
            return None
        if row["status"] == "cancelled":
            raise InquiryError("INQUIRY_ALREADY_CANCELLED")
        if row["status"] != "new" or int(row["version"]) != int(version):
            raise InquiryError("INQUIRY_STATUS_CONFLICT")
        db.execute(
            "UPDATE customer_inquiries SET status = 'cancelled', closed_at = CURRENT_TIMESTAMP, version = version + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (inquiry_id,),
        )
    return _load_inquiry(inquiry_id, "zh")


def _staff_scope_clause(actor_id: str, actor_role: str) -> Tuple[str, tuple]:
    if actor_role == "admin":
        return "", ()
    return " AND (i.assigned_to IS NULL OR i.assigned_to = ?)", (actor_id,)


def _staff_can_access(inquiry: Optional[Dict[str, Any]], actor_id: str, actor_role: str) -> bool:
    return bool(inquiry) and (actor_role == "admin" or inquiry.get("assigned_to") in (None, "", actor_id))


def list_staff_inquiries(
    actor_id: str,
    actor_role: str,
    page: int = 1,
    page_size: int = 20,
    query: str = "",
    status: str = "all",
    language: str = "zh",
) -> Dict[str, Any]:
    safe_page = max(int(page), 1)
    safe_size = min(max(int(page_size), 1), 50)
    selected_language = "en" if language == "en" else "zh"
    selected_status = str(status or "all")
    if selected_status != "all" and selected_status not in INQUIRY_STATES:
        raise InquiryError("INQUIRY_STATUS_CONFLICT")
    like = "%{}%".format(str(query or "").strip())
    scope, scope_params = _staff_scope_clause(actor_id, actor_role)
    filters = """
        FROM customer_inquiries i
        JOIN users creator ON creator.id = i.created_by
        LEFT JOIN users assignee ON assignee.id = i.assigned_to
        WHERE 1 = 1 {}
          AND (? = 'all' OR i.status = ?)
          AND (? = '%' OR i.inquiry_number LIKE ? OR creator.display_name LIKE ?
               OR creator.email LIKE ? OR creator.phone LIKE ? OR i.customer_name_snapshot LIKE ?)
    """.format(scope)
    params = (*scope_params, selected_status, selected_status, like, like, like, like, like, like)
    with get_connection() as db:
        total = int(db.execute("SELECT COUNT(*) " + filters, params).fetchone()[0])
        rows = db.execute(
            """
            SELECT i.*, creator.display_name AS customer_display_name,
                   creator.email AS customer_email_current, creator.phone AS customer_phone_current,
                   assignee.display_name AS assignee_name
            """ + filters + " ORDER BY CASE i.status WHEN 'new' THEN 0 WHEN 'assigned' THEN 1 ELSE 2 END, i.created_at DESC LIMIT ? OFFSET ?",
            (*params, safe_size, (safe_page - 1) * safe_size),
        ).fetchall()
        results = []
        for row in rows:
            record = dict(row)
            counts = db.execute(
                "SELECT item_type, COUNT(*) AS item_count, COALESCE(SUM(quantity), 0) AS quantity FROM customer_inquiry_items WHERE inquiry_id = ? GROUP BY item_type",
                (record["id"],),
            ).fetchall()
            record["item_summary"] = [dict(count) for count in counts]
            results.append(record)
    return {"items": results, "total": total, "page": safe_page, "page_size": safe_size, "language": selected_language}


def get_staff_inquiry(inquiry_id: str, actor_id: str, actor_role: str, language: str = "zh") -> Optional[Dict[str, Any]]:
    inquiry = _load_inquiry(inquiry_id, language)
    return inquiry if _staff_can_access(inquiry, actor_id, actor_role) else None


def update_staff_inquiry(
    inquiry_id: str,
    actor_id: str,
    actor_role: str,
    version: int,
    status: Optional[str] = None,
    assigned_to: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    inquiry = _load_inquiry(inquiry_id, "zh")
    if inquiry is None:
        return None
    if not _staff_can_access(inquiry, actor_id, actor_role):
        raise InquiryError("INQUIRY_ACCESS_DENIED")
    if int(inquiry.get("version") or 0) != int(version):
        raise InquiryError("INQUIRY_STATUS_CONFLICT")
    target_status = str(status or inquiry["status"])
    if target_status not in INQUIRY_STATES or target_status == "cancelled":
        raise InquiryError("INQUIRY_STATUS_CONFLICT")
    target_assignee = assigned_to if assigned_to is not None else inquiry.get("assigned_to")
    if actor_role != "admin" and assigned_to not in (None, "", actor_id):
        raise InquiryError("INQUIRY_ACCESS_DENIED")
    if target_assignee:
        with get_connection() as db:
            available = db.execute(
                "SELECT id FROM users WHERE id = ? AND role IN ('sales', 'admin') AND enabled = 1 AND deleted_at IS NULL",
                (target_assignee,),
            ).fetchone()
        if available is None:
            raise InquiryError("INQUIRY_ASSIGNEE_UNAVAILABLE")
    if target_status == "assigned" and not target_assignee:
        target_assignee = actor_id
    if target_status == "new" and target_assignee:
        target_status = "assigned"
    closed_at = "CURRENT_TIMESTAMP" if target_status in ("closed", "cancelled") else "NULL"
    with get_connection() as db:
        cursor = db.execute(
            """
            UPDATE customer_inquiries
            SET status = ?, assigned_to = ?, closed_at = {}, version = version + 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND version = ?
            """.format(closed_at),
            (target_status, target_assignee or None, inquiry_id, version),
        )
    if not cursor.rowcount:
        raise InquiryError("INQUIRY_STATUS_CONFLICT")
    return _load_inquiry(inquiry_id, "zh")


def inquiry_quote_items(inquiry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten an immutable inquiry snapshot into price-editable quote rows.

    Values intentionally begin at zero: sales can use the existing quote editor's
    auto-fill, then adjust commercial terms without mutating the inquiry snapshot.
    """
    rows: List[Dict[str, Any]] = []
    device_index = 0
    for entry in inquiry.get("items") or []:
        snapshot = entry.get("snapshot") or {}
        item_type = str(entry.get("item_type") or "device_config")
        quantity = max(1, int(entry.get("quantity") or 1))
        if item_type != "device_config":
            rows.append({
                "kind": item_type,
                "source_id": snapshot.get("option_id") or entry.get("source_id"),
                "name": snapshot.get("name") or entry.get("display_name") or "Untitled item",
                "device_label": "Service Tools" if item_type == "tool" else "Accessories",
                "code": snapshot.get("code") or "",
                "quantity": quantity,
                "price": 0,
                "price_cny": snapshot.get("price_cny") or 0,
                "price_usd": snapshot.get("price_usd") or 0,
            })
            continue
        device_index += 1
        product = snapshot.get("product") or {}
        label = "Device {} · {}".format(device_index, product.get("name") or product.get("id") or "—")
        rows.append({"kind": "product", "source_id": product.get("id"), "name": product.get("title_name") or product.get("name") or "Device", "device_label": label, "code": product.get("name") or product.get("id") or "", "quantity": 1, "price": 0, "price_cny": 0, "price_usd": 0})
        for category in snapshot.get("categories") or []:
            for option in category.get("options") or []:
                rows.append({"kind": "surcharge" if category.get("id") == "voltage" else "option", "source_id": option.get("id"), "name": option.get("name") or "Option", "device_label": label, "code": option.get("code") or "", "quantity": 1, "price": 0, "price_cny": option.get("price_cny") or option.get("price") or 0, "price_usd": option.get("price_usd") or 0})
    if not rows:
        raise InquiryError("INQUIRY_SNAPSHOT_INVALID")
    return rows


def mark_inquiry_quoted(inquiry_id: str, actor_id: str, actor_role: str, quote_id: str, version: int) -> Optional[Dict[str, Any]]:
    inquiry = _load_inquiry(inquiry_id, "zh")
    if inquiry is None:
        return None
    if not _staff_can_access(inquiry, actor_id, actor_role):
        raise InquiryError("INQUIRY_ACCESS_DENIED")
    if inquiry.get("converted_quote_id"):
        raise InquiryError("INQUIRY_QUOTE_ALREADY_EXISTS")
    if int(inquiry.get("version") or 0) != int(version):
        raise InquiryError("INQUIRY_STATUS_CONFLICT")
    with get_connection() as db:
        cursor = db.execute(
            """
            UPDATE customer_inquiries
            SET converted_quote_id = ?, status = 'quoted', assigned_to = COALESCE(assigned_to, ?),
                version = version + 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND version = ? AND converted_quote_id IS NULL
            """,
            (quote_id, actor_id, inquiry_id, version),
        )
    if not cursor.rowcount:
        raise InquiryError("INQUIRY_STATUS_CONFLICT")
    return _load_inquiry(inquiry_id, "zh")
