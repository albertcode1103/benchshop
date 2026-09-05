"""Quotation persistence with backwards-compatible legacy reads."""

import json
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .database import get_connection
from .security import to_iso, utc_now


def _normalize_quote_items(items: Any) -> List[Dict[str, Any]]:
    if not isinstance(items, list) or not items:
        raise ValueError("报价单至少需要一条项目")
    normalized: List[Dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError("第 {} 条报价项目格式不正确".format(index))
        try:
            quantity = int(float(item.get("quantity", 1)))
            price = float(item.get("price", 0))
        except (TypeError, ValueError):
            raise ValueError("第 {} 条报价的数量或单价格式不正确".format(index))
        if quantity < 1:
            raise ValueError("第 {} 条报价数量至少为 1".format(index))
        if not math.isfinite(price) or price < 0:
            raise ValueError("第 {} 条报价单价必须为非负数字".format(index))
        normalized_item = dict(item)
        normalized_item["quantity"] = quantity
        normalized_item["price"] = round(price, 2)
        normalized.append(normalized_item)
    return normalized


def _optional_text(value: Any, limit: int = 200) -> str:
    return str(value or "").strip()[:limit]


QUOTE_LIFECYCLE_STATES = {"draft", "sent", "archived"}


def _quote_number_prefix() -> str:
    return "BTQ-{}-".format(datetime.now(timezone.utc).strftime("%Y%m%d"))


def _allocate_quote_number(db) -> str:
    """Allocate the next human-readable number while SQLite holds the write lock."""
    prefix = _quote_number_prefix()
    rows = db.execute(
        "SELECT quote_number FROM commerce_quotes WHERE quote_number LIKE ? ORDER BY quote_number DESC LIMIT 1",
        (prefix + "%",),
    ).fetchall()
    last = 0
    if rows and rows[0]["quote_number"]:
        suffix = str(rows[0]["quote_number"])[len(prefix):]
        try:
            last = int(suffix)
        except ValueError:
            last = 0
    return "{}{:04d}".format(prefix, last + 1)


def _decode_revision(row) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    payload = json.loads(row["snapshot_json"])
    quote = dict(payload.get("quote") or {})
    if not quote:
        return None
    quote["revision"] = {
        "id": row["id"],
        "revision_number": int(row["revision_number"]),
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    }
    quote["document_version"] = 2
    return quote


def _create_quote_revision(db, quote_id: str, created_by: str) -> Dict[str, Any]:
    quote_row = db.execute("SELECT * FROM commerce_quotes WHERE id = ?", (quote_id,)).fetchone()
    if quote_row is None:
        raise ValueError("Quote not found")
    quote = _decode(quote_row, document_version=2)
    next_number = int(
        db.execute("SELECT COALESCE(MAX(revision_number), 0) + 1 FROM quote_revisions WHERE quote_id = ?", (quote_id,)).fetchone()[0]
    )
    revision_id = uuid.uuid4().hex
    quote["revision_number"] = next_number
    quote["revision_created_at"] = to_iso(utc_now())
    db.execute(
        "INSERT INTO quote_revisions (id, quote_id, revision_number, snapshot_json, created_by) VALUES (?, ?, ?, ?, ?)",
        (revision_id, quote_id, next_number, json.dumps({"schema_version": 1, "quote": quote}, ensure_ascii=False, allow_nan=False), created_by),
    )
    row = db.execute("SELECT * FROM quote_revisions WHERE id = ?", (revision_id,)).fetchone()
    return dict(row)


def get_quote_revision(revision_id: str) -> Optional[Dict[str, Any]]:
    if not revision_id:
        return None
    with get_connection() as db:
        row = db.execute("SELECT * FROM quote_revisions WHERE id = ?", (revision_id,)).fetchone()
    return _decode_revision(row)


def save_quote(
    config_id: Optional[str],
    user_id: str,
    title: str,
    items: List[Dict[str, Any]],
    total_price: Any,
    quote_id: Optional[str] = None,
    currency: str = "CNY",
    source_share_id: Optional[str] = None,
    customer_name: str = "",
    customer_email: str = "",
    language: str = "zh",
    allow_any_owner: bool = False,
) -> Dict[str, Any]:
    normalized_items = _normalize_quote_items(items)
    try:
        requested_total = float(total_price)
    except (TypeError, ValueError):
        raise ValueError("报价总价格式不正确")
    if not math.isfinite(requested_total) or requested_total < 0:
        raise ValueError("报价总价格式不正确")
    if currency not in ("CNY", "USD"):
        raise ValueError("报价货币仅支持人民币或美元")

    calculated_total = round(sum(item["quantity"] * item["price"] for item in normalized_items), 2)
    selected_language = "en" if language == "en" else "zh"
    clean_config_id = _optional_text(config_id, 100) or None
    clean_source_share_id = _optional_text(source_share_id, 100) or None
    clean_title = _optional_text(title, 200) or ("Quotation" if selected_language == "en" else "配置报价单")

    with get_connection() as db:
        if clean_config_id:
            exists = db.execute("SELECT id FROM saved_configs WHERE id = ?", (clean_config_id,)).fetchone()
            if not exists:
                raise ValueError("Configuration not found")

        # Only the new share table is a valid foreign-key target here. Quotes
        # created from legacy shares remain editable, without an invalid link.
        if clean_source_share_id:
            share = db.execute("SELECT id FROM commerce_shares WHERE id = ?", (clean_source_share_id,)).fetchone()
            if share is None:
                clean_source_share_id = None

        if quote_id:
            new_row = db.execute("SELECT user_id, lifecycle_status FROM commerce_quotes WHERE id = ?", (quote_id,)).fetchone()
            if new_row is not None:
                if not allow_any_owner and new_row["user_id"] != user_id:
                    raise ValueError("Quote access denied")
                if new_row["lifecycle_status"] == "archived":
                    raise ValueError("Quote archived")
                db.execute(
                    """
                    UPDATE commerce_quotes
                    SET config_id = ?, source_share_id = ?, title = ?,
                        customer_name = ?, customer_email = ?, language = ?,
                        items_json = ?, total_price = ?, currency = ?,
                        version = version + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        clean_config_id,
                        clean_source_share_id,
                        clean_title,
                        _optional_text(customer_name, 200),
                        _optional_text(customer_email, 320),
                        selected_language,
                        json.dumps(normalized_items, ensure_ascii=False, allow_nan=False),
                        calculated_total,
                        currency,
                        quote_id,
                    ),
                )
                row = db.execute("SELECT * FROM commerce_quotes WHERE id = ?", (quote_id,)).fetchone()
                return _decode(row, document_version=2)

            legacy_row = db.execute("SELECT user_id FROM quotes WHERE id = ?", (quote_id,)).fetchone()
            if legacy_row is None:
                raise ValueError("Quote not found")
            if not allow_any_owner and legacy_row["user_id"] != user_id:
                raise ValueError("Quote access denied")
            if clean_config_id is None:
                raise ValueError("Configuration not found")
            db.execute(
                """
                UPDATE quotes
                SET config_id = ?, title = ?, items_json = ?, total_price = ?,
                    currency = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    clean_config_id,
                    clean_title,
                    json.dumps(normalized_items, ensure_ascii=False, allow_nan=False),
                    calculated_total,
                    currency,
                    quote_id,
                ),
            )
            row = db.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,)).fetchone()
            return _decode(row, document_version=1)

        new_quote_id = uuid.uuid4().hex
        db.execute(
            """
            INSERT INTO commerce_quotes
                (id, config_id, source_share_id, user_id, title,
                 customer_name, customer_email, language, items_json,
                 total_price, currency)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_quote_id,
                clean_config_id,
                clean_source_share_id,
                user_id,
                clean_title,
                _optional_text(customer_name, 200),
                _optional_text(customer_email, 320),
                selected_language,
                json.dumps(normalized_items, ensure_ascii=False, allow_nan=False),
                calculated_total,
                currency,
            ),
        )
        row = db.execute("SELECT * FROM commerce_quotes WHERE id = ?", (new_quote_id,)).fetchone()
    return _decode(row, document_version=2)


def _decode(row, document_version: int = 2):
    if not row:
        return None
    result = dict(row)
    result["items"] = json.loads(result.pop("items_json"))
    result.setdefault("source_share_id", None)
    result.setdefault("customer_name", "")
    result.setdefault("customer_email", "")
    result.setdefault("language", "zh")
    result["document_version"] = document_version
    return result


def list_quotes(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    restriction = "WHERE q.user_id = ?" if user_id else ""
    params = (user_id,) if user_id else ()
    with get_connection() as db:
        new_rows = db.execute(
            """
            SELECT q.*, u.display_name, u.email, u.phone
            FROM commerce_quotes q JOIN users u ON u.id = q.user_id
            {} ORDER BY q.updated_at DESC
            """.format(restriction),
            params,
        ).fetchall()
        legacy_rows = db.execute(
            """
            SELECT q.*, u.display_name, u.email, u.phone
            FROM quotes q JOIN users u ON u.id = q.user_id
            {} ORDER BY q.updated_at DESC
            """.format(restriction),
            params,
        ).fetchall()
        delivery_rows = db.execute(
            """
            SELECT d.quote_id, COUNT(*) AS delivery_count,
                   GROUP_CONCAT(COALESCE(NULLIF(u.display_name, ''), u.email, u.phone), ', ') AS recipient_summary
            FROM quote_deliveries d
            JOIN users u ON u.id = d.recipient_user_id
            WHERE d.status = 'delivered'
            GROUP BY d.quote_id
            """
        ).fetchall()
    delivery_map = {row["quote_id"]: dict(row) for row in delivery_rows}
    results = [_decode(row, 2) for row in new_rows] + [_decode(row, 1) for row in legacy_rows]
    for item in results:
        item.update(delivery_map.get(item["id"], {"delivery_count": 0, "recipient_summary": ""}))
    return sorted(results, key=lambda item: str(item.get("updated_at") or ""), reverse=True)


def get_quote(quote_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    owner_clause = "AND user_id = ?" if user_id else ""
    params = (quote_id, user_id) if user_id else (quote_id,)
    with get_connection() as db:
        row = db.execute("SELECT * FROM commerce_quotes WHERE id = ? {}".format(owner_clause), params).fetchone()
        if row is not None:
            return _decode(row, 2)
        row = db.execute("SELECT * FROM quotes WHERE id = ? {}".format(owner_clause), params).fetchone()
    return _decode(row, 1)


def _share_owner(db, share_id: Optional[str]) -> Optional[str]:
    if not share_id:
        return None
    row = db.execute("SELECT created_by FROM commerce_shares WHERE id = ?", (share_id,)).fetchone()
    if row is None:
        row = db.execute("SELECT created_by FROM config_shares WHERE id = ?", (share_id,)).fetchone()
    return row["created_by"] if row else None


def deliver_quote(
    quote_id: str,
    delivered_by: str,
    recipient_user_id: Optional[str] = None,
    source_share_id: Optional[str] = None,
) -> Dict[str, Any]:
    quote = get_quote(quote_id)
    if quote is None:
        raise ValueError("Quote not found")
    document_version = int(quote.get("document_version") or 2)
    resolved_share_id = _optional_text(source_share_id or quote.get("source_share_id"), 100) or None
    with get_connection() as db:
        recipient_id = _optional_text(recipient_user_id, 100) or _share_owner(db, resolved_share_id)
        if not recipient_id:
            raise ValueError("Quote recipient required")
        recipient = db.execute(
            "SELECT id, display_name, email, phone, role, enabled, deleted_at FROM users WHERE id = ?",
            (recipient_id,),
        ).fetchone()
        if recipient is None or recipient["role"] != "customer" or not recipient["enabled"] or recipient["deleted_at"]:
            raise ValueError("Quote recipient unavailable")
        revision_id = None
        if document_version == 2:
            current = db.execute(
                "SELECT lifecycle_status, quote_number FROM commerce_quotes WHERE id = ?",
                (quote_id,),
            ).fetchone()
            if current is None:
                raise ValueError("Quote not found")
            if current["lifecycle_status"] == "archived":
                raise ValueError("Quote archived")
            quote_number = current["quote_number"] or _allocate_quote_number(db)
            db.execute(
                """
                UPDATE commerce_quotes
                SET quote_number = ?, lifecycle_status = 'sent',
                    sent_at = COALESCE(sent_at, CURRENT_TIMESTAMP),
                    version = version + 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (quote_number, quote_id),
            )
            revision_id = _create_quote_revision(db, quote_id, delivered_by)["id"]

        existing = db.execute(
            "SELECT id FROM quote_deliveries WHERE quote_id = ? AND recipient_user_id = ?",
            (quote_id, recipient_id),
        ).fetchone()
        if existing:
            delivery_id = existing["id"]
            db.execute(
                """
                UPDATE quote_deliveries
                SET document_version = ?, revision_id = ?, source_share_id = ?, delivered_by = ?,
                    status = 'delivered', delivered_at = CURRENT_TIMESTAMP,
                    viewed_at = NULL, withdrawn_at = NULL,
                    last_viewed_revision_id = NULL, notification_state = 'unread'
                WHERE id = ?
                """,
                (document_version, revision_id, resolved_share_id, delivered_by, delivery_id),
            )
        else:
            delivery_id = uuid.uuid4().hex
            db.execute(
                """
                INSERT INTO quote_deliveries
                    (id, quote_id, document_version, revision_id, recipient_user_id,
                     source_share_id, delivered_by, notification_state)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'unread')
                """,
                (delivery_id, quote_id, document_version, revision_id, recipient_id, resolved_share_id, delivered_by),
            )
        row = db.execute("SELECT * FROM quote_deliveries WHERE id = ?", (delivery_id,)).fetchone()
    result = dict(row)
    result["recipient"] = {
        "id": recipient["id"], "display_name": recipient["display_name"],
        "email": recipient["email"], "phone": recipient["phone"],
    }
    return result


def withdraw_quote_delivery(quote_id: str, recipient_user_id: Optional[str] = None) -> int:
    parameters: List[Any] = [quote_id]
    recipient_clause = ""
    if recipient_user_id:
        recipient_clause = " AND recipient_user_id = ?"
        parameters.append(recipient_user_id)
    with get_connection() as db:
        cursor = db.execute(
            "UPDATE quote_deliveries SET status = 'withdrawn', withdrawn_at = CURRENT_TIMESTAMP WHERE quote_id = ? AND status = 'delivered'{}".format(recipient_clause),
            parameters,
        )
    return cursor.rowcount


def archive_quote(
    quote_id: str,
    archived_by: str,
    *,
    user_id: Optional[str] = None,
    expected_version: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Archive a quote without removing its deliveries or immutable revisions.

    A sent quotation remains available to its recipient through the revision that
    was delivered.  Archiving only prevents staff from editing or re-sending the
    working document until it is explicitly restored.
    """
    owner_clause = "AND user_id = ?" if user_id else ""
    parameters: List[Any] = [quote_id]
    if user_id:
        parameters.append(user_id)
    with get_connection() as db:
        row = db.execute(
            "SELECT * FROM commerce_quotes WHERE id = ? {}".format(owner_clause), parameters
        ).fetchone()
        if row is None:
            return None
        if row["lifecycle_status"] == "archived":
            raise ValueError("Quote already archived")
        if expected_version is not None and int(row["version"] or 1) != int(expected_version):
            raise ValueError("Quote version conflict")
        db.execute(
            """
            UPDATE commerce_quotes
            SET lifecycle_status = 'archived', archived_at = CURRENT_TIMESTAMP,
                archived_by = ?, version = version + 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (archived_by, quote_id),
        )
        saved = db.execute("SELECT * FROM commerce_quotes WHERE id = ?", (quote_id,)).fetchone()
    return _decode(saved, document_version=2)


def restore_quote(
    quote_id: str,
    restored_by: str,
    *,
    user_id: Optional[str] = None,
    expected_version: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Restore an archived quote to its appropriate editable lifecycle state."""
    owner_clause = "AND user_id = ?" if user_id else ""
    parameters: List[Any] = [quote_id]
    if user_id:
        parameters.append(user_id)
    with get_connection() as db:
        row = db.execute(
            "SELECT * FROM commerce_quotes WHERE id = ? {}".format(owner_clause), parameters
        ).fetchone()
        if row is None:
            return None
        if row["lifecycle_status"] != "archived":
            raise ValueError("Quote not archived")
        if expected_version is not None and int(row["version"] or 1) != int(expected_version):
            raise ValueError("Quote version conflict")
        # A previously delivered quote returns to sent; otherwise it remains an
        # editable draft.  The original delivery history is deliberately kept.
        delivered = db.execute(
            "SELECT 1 FROM quote_deliveries WHERE quote_id = ? LIMIT 1", (quote_id,)
        ).fetchone()
        restored_status = "sent" if delivered else "draft"
        db.execute(
            """
            UPDATE commerce_quotes
            SET lifecycle_status = ?, archived_at = NULL, archived_by = NULL,
                version = version + 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (restored_status, quote_id),
        )
        saved = db.execute("SELECT * FROM commerce_quotes WHERE id = ?", (quote_id,)).fetchone()
    return _decode(saved, document_version=2)


def quote_history(quote_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Return audit-friendly immutable revision and delivery history for staff."""
    owner_clause = "AND q.user_id = ?" if user_id else ""
    parameters: List[Any] = [quote_id]
    if user_id:
        parameters.append(user_id)
    with get_connection() as db:
        quote = db.execute(
            "SELECT q.* FROM commerce_quotes q WHERE q.id = ? {}".format(owner_clause), parameters
        ).fetchone()
        if quote is None:
            return None
        revisions = db.execute(
            """
            SELECT r.id, r.revision_number, r.created_at,
                   COALESCE(NULLIF(u.display_name, ''), u.email, u.phone, r.created_by) AS created_by_name
            FROM quote_revisions r LEFT JOIN users u ON u.id = r.created_by
            WHERE r.quote_id = ? ORDER BY r.revision_number DESC
            """,
            (quote_id,),
        ).fetchall()
        deliveries = db.execute(
            """
            SELECT d.id, d.status, d.delivered_at, d.withdrawn_at, d.viewed_at,
                   d.notification_state, r.revision_number,
                   COALESCE(NULLIF(recipient.display_name, ''), recipient.email, recipient.phone, d.recipient_user_id) AS recipient_name,
                   COALESCE(NULLIF(sender.display_name, ''), sender.email, sender.phone, d.delivered_by) AS delivered_by_name
            FROM quote_deliveries d
            LEFT JOIN quote_revisions r ON r.id = d.revision_id
            LEFT JOIN users recipient ON recipient.id = d.recipient_user_id
            LEFT JOIN users sender ON sender.id = d.delivered_by
            WHERE d.quote_id = ? ORDER BY d.delivered_at DESC, d.id DESC
            """,
            (quote_id,),
        ).fetchall()
    return {
        "quote": _decode(quote, document_version=2),
        "revisions": [dict(row) for row in revisions],
        "deliveries": [dict(row) for row in deliveries],
    }


def list_customer_quotes(user_id: str) -> List[Dict[str, Any]]:
    with get_connection() as db:
        deliveries = db.execute(
            """
            SELECT d.*, u.display_name AS sender_name, u.email AS sender_email,
                   u.phone AS sender_phone
            FROM quote_deliveries d
            LEFT JOIN users u ON u.id = d.delivered_by
            WHERE d.recipient_user_id = ? AND d.status = 'delivered'
            ORDER BY d.delivered_at DESC
            """,
            (user_id,),
        ).fetchall()
    results = []
    for delivery in deliveries:
        delivery_data = dict(delivery)
        revision_id = str(delivery_data.get("revision_id") or "")
        quote = get_quote_revision(revision_id) if revision_id else get_quote(delivery_data["quote_id"])
        if quote is None:
            continue
        quote["delivery"] = delivery_data
        quote["sender"] = {
            "display_name": delivery_data.pop("sender_name", "") or "",
            "email": delivery_data.pop("sender_email", "") or "",
            "phone": delivery_data.pop("sender_phone", "") or "",
        }
        quote["unread"] = (
            bool(revision_id) and delivery_data.get("last_viewed_revision_id") != revision_id
        ) or (not revision_id and (not delivery_data.get("viewed_at") or str(quote.get("updated_at") or "") > str(delivery_data.get("viewed_at") or "")))
        results.append(quote)
    return results


def get_customer_quote(quote_id: str, user_id: str, mark_viewed: bool = False) -> Optional[Dict[str, Any]]:
    with get_connection() as db:
        delivery = db.execute(
            """
            SELECT d.*, u.display_name AS sender_name, u.email AS sender_email,
                   u.phone AS sender_phone
            FROM quote_deliveries d
            LEFT JOIN users u ON u.id = d.delivered_by
            WHERE d.quote_id = ? AND d.recipient_user_id = ? AND d.status = 'delivered'
            """,
            (quote_id, user_id),
        ).fetchone()
        if delivery is None:
            return None
        if mark_viewed:
            db.execute(
                "UPDATE quote_deliveries SET viewed_at = CURRENT_TIMESTAMP, last_viewed_revision_id = revision_id, notification_state = 'read' WHERE id = ?",
                (delivery["id"],),
            )
    revision_id = str(delivery["revision_id"] or "")
    result = get_quote_revision(revision_id) if revision_id else get_quote(quote_id)
    if result is None:
        return None
    delivery_data = dict(delivery)
    if mark_viewed:
        delivery_data["viewed_at"] = to_iso(utc_now())
        delivery_data["last_viewed_revision_id"] = revision_id or None
        delivery_data["notification_state"] = "read"
    result["delivery"] = delivery_data
    result["sender"] = {
        "display_name": delivery_data.pop("sender_name", "") or "",
        "email": delivery_data.pop("sender_email", "") or "",
        "phone": delivery_data.pop("sender_phone", "") or "",
    }
    result["unread"] = False if mark_viewed else (
        (bool(revision_id) and delivery_data.get("last_viewed_revision_id") != revision_id)
        or (not revision_id and (not delivery_data.get("viewed_at") or str(result.get("updated_at") or "") > str(delivery_data.get("viewed_at") or "")))
    )
    return result


def delete_quote(quote_id: str, user_id: Optional[str] = None) -> bool:
    owner_clause = "AND user_id = ?" if user_id else ""
    params = (quote_id, user_id) if user_id else (quote_id,)
    with get_connection() as db:
        commerce = db.execute("SELECT lifecycle_status FROM commerce_quotes WHERE id = ? {}".format(owner_clause), params).fetchone()
        if commerce is not None:
            if commerce["lifecycle_status"] != "draft":
                raise ValueError("Quote sent deletion forbidden")
            cursor = db.execute("DELETE FROM commerce_quotes WHERE id = ? {}".format(owner_clause), params)
            return bool(cursor.rowcount)
        delivery = db.execute("SELECT 1 FROM quote_deliveries WHERE quote_id = ? LIMIT 1", (quote_id,)).fetchone()
        if delivery is not None:
            raise ValueError("Quote sent deletion forbidden")
        cursor = db.execute("DELETE FROM quotes WHERE id = ? {}".format(owner_clause), params)
    return cursor.rowcount > 0


def list_reference_prices() -> Dict[str, List[Dict[str, Any]]]:
    with get_connection() as db:
        products = db.execute("SELECT id, name, base_price, price_usd FROM products WHERE enabled = 1").fetchall()
        options = db.execute("SELECT id, code, name, price, price_usd FROM options WHERE enabled = 1").fetchall()
    return {"products": [dict(row) for row in products], "options": [dict(row) for row in options]}
