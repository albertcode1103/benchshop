"""Quotation persistence with backwards-compatible legacy reads."""

import json
import math
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from .database import get_connection
from .security import to_iso, utc_now
from .quote_categories import recover_quote_categories


QUOTE_ITEM_FIELDS = frozenset({
    'kind', 'line_id', 'source_id', 'id', 'name', 'name_en', 'display_name', 'code',
    'device_label', 'device_key', 'parent_device_key', 'device_sequence',
    'quantity', 'price', 'quoted_price', 'reference_price', 'price_cny', 'price_usd',
    'price_overridden', 'locked', 'configuration_role', 'device_specifications',
    'category_id', 'category_name', 'category_name_en', 'category_label', 'category_sort_order',
    'catalog_category_sort_order', 'sort_order', 'catalog_sort_order',
    'availability', 'captured_availability', 'availability_details',
})


def _normalize_quote_items(items: Any, currency: str = "CNY") -> List[Dict[str, Any]]:
    if not isinstance(items, list) or not items:
        raise ValueError("报价单至少需要一条项目")
    normalized: List[Dict[str, Any]] = []
    current_device_key: Optional[str] = None
    current_device_sequence = 0
    allowed_kinds = {"product", "option", "surcharge", "tool", "accessory"}
    allowed_availability = {"active", "inactive", "missing", "snapshot_only"}
    def safe_non_negative_int(value: Any, fallback: int = 0) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError, OverflowError):
            return fallback

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError("第 {} 条报价项目格式不正确".format(index))
        try:
            quantity = int(float(item.get("quantity", 1)))
            price = float(item.get("price", 0))
        except (TypeError, ValueError, OverflowError):
            raise ValueError("第 {} 条报价的数量或单价格式不正确".format(index))
        if quantity < 1:
            raise ValueError("第 {} 条报价数量至少为 1".format(index))
        if not math.isfinite(price) or price < 0:
            raise ValueError("第 {} 条报价单价必须为非负数字".format(index))
        normalized_item = {key: value for key, value in item.items() if key in QUOTE_ITEM_FIELDS}
        kind = str(normalized_item.get("kind") or "option").strip().lower()
        if kind not in allowed_kinds:
            raise ValueError("第 {} 条报价项目类型不正确".format(index))
        line_id = _optional_text(normalized_item.get("line_id"), 100) or uuid.uuid4().hex
        availability = str(normalized_item.get("availability") or "active").strip().lower()
        if availability not in allowed_availability:
            availability = "snapshot_only"
        if kind == "product":
            current_device_sequence += 1
            current_device_sequence = max(1, safe_non_negative_int(normalized_item.get("device_sequence"), current_device_sequence))
            current_device_key = _optional_text(normalized_item.get("device_key"), 100) or "device-{}-{}".format(current_device_sequence, line_id[:8])
            normalized_item["device_key"] = current_device_key
            normalized_item["parent_device_key"] = None
            normalized_item["device_sequence"] = current_device_sequence
        elif kind in ("option", "surcharge"):
            parent_key = _optional_text(normalized_item.get("parent_device_key"), 100) or current_device_key
            normalized_item["parent_device_key"] = parent_key
            normalized_item["device_sequence"] = safe_non_negative_int(normalized_item.get("device_sequence"), current_device_sequence)
        else:
            normalized_item["parent_device_key"] = None
            normalized_item["device_sequence"] = 0
        reference_price = normalized_item.get("reference_price")
        if reference_price is None:
            reference_price = normalized_item.get("price_usd" if currency == "USD" else "price_cny", price)
        try:
            clean_reference_price = float(reference_price or 0)
        except (TypeError, ValueError, OverflowError):
            clean_reference_price = 0
        if not math.isfinite(clean_reference_price) or clean_reference_price < 0:
            clean_reference_price = 0
        normalized_item["kind"] = kind
        normalized_item["line_id"] = line_id
        normalized_item["availability"] = availability
        normalized_item["quantity"] = quantity
        normalized_item["price"] = round(price, 2)
        normalized_item["quoted_price"] = round(price, 2)
        normalized_item["reference_price"] = round(clean_reference_price, 2)
        normalized_item["price_overridden"] = bool(normalized_item.get("price_overridden")) or abs(price - clean_reference_price) >= 0.005
        normalized.append(normalized_item)
    device_sequences: Dict[str, int] = {}
    for item in normalized:
        if item.get("kind") != "product":
            continue
        device_key = str(item.get("device_key") or "")
        if device_key in device_sequences:
            raise ValueError("报价设备标识重复")
        device_sequences[device_key] = int(item.get("device_sequence") or 0)
    for index, item in enumerate(normalized, start=1):
        if item.get("kind") not in ("option", "surcharge"):
            continue
        parent_key = item.get("parent_device_key")
        if parent_key and parent_key not in device_sequences:
            raise ValueError("第 {} 条配置找不到所属设备".format(index))
        if parent_key:
            item["device_sequence"] = device_sequences[parent_key]
    return _canonical_quote_items(normalized)


def _canonical_quote_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep device groups stable, then tools and accessories in catalog order."""
    def item_type(item: Dict[str, Any]) -> str:
        kind = str(item.get("kind") or "")
        if kind == "tool":
            return "tool"
        if kind == "accessory":
            return "accessory"
        return "device_config"

    def safe_order(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError, OverflowError):
            return 2147483647

    indexed = list(enumerate(items))
    ranks = {"device_config": 0, "tool": 1, "accessory": 2}
    indexed.sort(key=lambda pair: (
        ranks[item_type(pair[1])],
        safe_order(pair[1].get("device_sequence")) if item_type(pair[1]) == "device_config" else safe_order(pair[1].get("category_sort_order", pair[1].get("catalog_category_sort_order"))),
        0 if pair[1].get("kind") == "product" else 1 if item_type(pair[1]) == "device_config" else safe_order(pair[1].get("sort_order", pair[1].get("catalog_sort_order"))),
        safe_order(pair[1].get("category_sort_order", pair[1].get("catalog_category_sort_order"))) if item_type(pair[1]) == "device_config" else str(pair[1].get("code") or ""),
        safe_order(pair[1].get("sort_order", pair[1].get("catalog_sort_order"))) if item_type(pair[1]) == "device_config" else pair[0],
        pair[0],
    ))
    return [item for _, item in indexed]


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
    source_inquiry_id: Optional[str] = None,
    source_type: str = "direct",
    source_document_version: Optional[int] = None,
    source_document_id: Optional[str] = None,
    source_code: str = "",
    customer_name: str = "",
    customer_email: str = "",
    customer_phone: str = "",
    language: str = "zh",
    allow_any_owner: bool = False,
    expected_version: Optional[int] = None,
    customer_address: str = "",
) -> Dict[str, Any]:
    if currency not in ("CNY", "USD"):
        raise ValueError("报价货币仅支持人民币或美元")
    normalized_items = _normalize_quote_items(items, currency)
    try:
        requested_total = float(total_price)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("报价总价格式不正确")
    if not math.isfinite(requested_total) or requested_total < 0:
        raise ValueError("报价总价格式不正确")
    try:
        calculated_total = round(sum(item["quantity"] * item["price"] for item in normalized_items), 2)
    except OverflowError:
        raise ValueError("报价计算总额超出支持范围")
    if not math.isfinite(calculated_total):
        raise ValueError("报价计算总额超出支持范围")
    selected_language = "en" if language == "en" else "zh"
    clean_config_id = _optional_text(config_id, 100) or None
    clean_source_share_id = _optional_text(source_share_id, 100) or None
    clean_source_inquiry_id = _optional_text(source_inquiry_id, 100) or None
    clean_source_type = str(source_type or "direct").strip().lower()
    if clean_source_type not in ("direct", "share", "inquiry"):
        raise ValueError("Quote source invalid")
    clean_source_document_id = _optional_text(source_document_id, 100) or None
    if clean_source_type == "inquiry":
        clean_source_document_id = clean_source_document_id or clean_source_inquiry_id
    elif clean_source_type == "share":
        clean_source_document_id = clean_source_document_id or clean_source_share_id
    elif clean_source_document_id:
        raise ValueError("Quote source invalid")
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
        if clean_source_inquiry_id:
            inquiry = db.execute("SELECT id FROM customer_inquiries WHERE id = ?", (clean_source_inquiry_id,)).fetchone()
            if inquiry is None:
                clean_source_inquiry_id = None

        if quote_id:
            new_row = db.execute(
                "SELECT user_id, lifecycle_status, version, quote_number FROM commerce_quotes WHERE id = ?",
                (quote_id,),
            ).fetchone()
            if new_row is not None:
                if not allow_any_owner and new_row["user_id"] != user_id:
                    raise ValueError("Quote access denied")
                if new_row["lifecycle_status"] == "archived":
                    raise ValueError("Quote archived")
                if expected_version is None or int(new_row["version"] or 1) != int(expected_version):
                    raise ValueError("Quote version conflict")
                quote_number = new_row["quote_number"] or _allocate_quote_number(db)
                try:
                    cursor = db.execute(
                        """
                        UPDATE commerce_quotes
                        SET quote_number = ?, config_id = ?, source_share_id = ?, source_inquiry_id = ?,
                            source_type = ?, source_document_version = ?, source_document_id = ?, source_code = ?, title = ?,
                            customer_name = ?, customer_email = ?, customer_phone = ?, customer_address = ?, language = ?,
                            items_json = ?, total_price = ?, currency = ?,
                            version = version + 1, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND version = ?
                        """,
                        (
                            quote_number,
                            clean_config_id,
                            clean_source_share_id,
                            clean_source_inquiry_id,
                            clean_source_type,
                            source_document_version,
                            clean_source_document_id,
                            _optional_text(source_code, 100),
                            clean_title,
                            _optional_text(customer_name, 200),
                            _optional_text(customer_email, 320),
                            _optional_text(customer_phone, 80),
                            _optional_text(customer_address, 500),
                            selected_language,
                            json.dumps(normalized_items, ensure_ascii=False, allow_nan=False),
                            calculated_total,
                            currency,
                            quote_id,
                            expected_version,
                        ),
                    )
                except sqlite3.IntegrityError as error:
                    if clean_source_type in ("share", "inquiry") and clean_source_document_id:
                        raise ValueError("Quote source already exists") from error
                    raise
                if not cursor.rowcount:
                    raise ValueError("Quote version conflict")
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
        quote_number = _allocate_quote_number(db)
        try:
            db.execute(
                """
                INSERT INTO commerce_quotes
                    (id, quote_number, config_id, source_share_id, source_inquiry_id,
                     source_type, source_document_version, source_document_id, source_code,
                     user_id, title,
                     customer_name, customer_email, customer_phone, customer_address, language, items_json,
                     total_price, currency)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_quote_id,
                    quote_number,
                    clean_config_id,
                    clean_source_share_id,
                    clean_source_inquiry_id,
                    clean_source_type,
                    source_document_version,
                    clean_source_document_id,
                    _optional_text(source_code, 100),
                    user_id,
                    clean_title,
                    _optional_text(customer_name, 200),
                    _optional_text(customer_email, 320),
                    _optional_text(customer_phone, 80),
                    _optional_text(customer_address, 500),
                    selected_language,
                    json.dumps(normalized_items, ensure_ascii=False, allow_nan=False),
                    calculated_total,
                    currency,
                ),
            )
        except sqlite3.IntegrityError as error:
            if clean_source_type in ("share", "inquiry") and clean_source_document_id:
                raise ValueError("Quote source already exists") from error
            raise
        row = db.execute("SELECT * FROM commerce_quotes WHERE id = ?", (new_quote_id,)).fetchone()
    return _decode(row, document_version=2)


def _decode(row, document_version: int = 2):
    if not row:
        return None
    result = dict(row)
    raw_items = json.loads(result.pop("items_json"))
    hydrated_items = []
    for index, item in enumerate(raw_items, start=1):
        hydrated = dict(item) if isinstance(item, dict) else {"name": str(item)}
        hydrated.setdefault("line_id", "legacy-{}-{}".format(str(result.get("id") or "quote")[:8], index))
        hydrated_items.append(hydrated)
    try:
        result["items"] = _normalize_quote_items(hydrated_items, result.get("currency") or "CNY")
    except ValueError:
        # A malformed historical snapshot remains inspectable; validation is
        # deliberately enforced only if staff choose to save it again.
        result["items"] = hydrated_items
    result.setdefault("source_share_id", None)
    result.setdefault("source_inquiry_id", None)
    result.setdefault("source_type", "direct")
    result.setdefault("source_document_version", None)
    result.setdefault("source_document_id", None)
    result.setdefault("source_code", "")
    result.setdefault("customer_name", "")
    result.setdefault("customer_email", "")
    result.setdefault("customer_phone", "")
    result.setdefault("customer_address", "")
    result.setdefault("language", "zh")
    result["document_version"] = document_version
    return result


def list_quotes(
    user_id: Optional[str] = None,
    status_filter: str = "all",
    include_archived: bool = True,
    query: str = "",
    due: bool = False,
) -> List[Dict[str, Any]]:
    restriction = "WHERE q.user_id = ?" if user_id else ""
    params = (user_id,) if user_id else ()
    with get_connection() as db:
        new_rows = db.execute(
            """
            SELECT q.*, u.display_name, u.email, u.phone,
                   COALESCE(NULLIF(q.customer_phone, ''),
                       (SELECT i.customer_phone_snapshot FROM customer_inquiries i WHERE i.id = q.source_inquiry_id),
                       (SELECT customer.phone FROM commerce_shares s JOIN users customer ON customer.id = s.created_by WHERE s.id = q.source_share_id),
                       ''
                   ) AS resolved_customer_phone
            FROM commerce_quotes q JOIN users u ON u.id = q.user_id
            {} ORDER BY q.updated_at DESC
            """.format(restriction),
            params,
        ).fetchall()
        legacy_rows = db.execute(
            """
            SELECT q.*, u.display_name, u.email, u.phone, '' AS customer_phone
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
        if due:
            from .dashboard_rules import due_quote_order, utc_now
            due_order = due_quote_order(db, utc_now())
            new_rows = [row for row in new_rows if row["id"] in due_order]
            legacy_rows = []
    delivery_map = {row["quote_id"]: dict(row) for row in delivery_rows}
    results = [_decode(row, 2) for row in new_rows] + [_decode(row, 1) for row in legacy_rows]
    for item in results:
        item.setdefault("lifecycle_status", "draft")
        if not item.get("customer_phone"):
            item["customer_phone"] = item.pop("resolved_customer_phone", "")
        item.update(delivery_map.get(item["id"], {"delivery_count": 0, "recipient_summary": ""}))
    if not include_archived:
        results = [item for item in results if item["lifecycle_status"] != "archived"]
    if status_filter != "all":
        results = [item for item in results if item["lifecycle_status"] == status_filter]
    search = str(query or "").strip().casefold()
    if search:
        searchable_fields = (
            "quote_number", "title", "customer_name", "customer_email", "customer_phone",
            "source_code", "display_name", "email", "phone", "recipient_summary",
        )
        results = [item for item in results if any(search in str(item.get(field) or "").casefold() for field in searchable_fields)]
    if due:
        return sorted(results, key=lambda item: due_order[item["id"]])
    return sorted(results, key=lambda item: str(item.get("updated_at") or ""), reverse=True)


def get_quote(quote_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    owner_clause = "AND q.user_id = ?" if user_id else ""
    params = (quote_id, user_id) if user_id else (quote_id,)
    with get_connection() as db:
        row = db.execute(
            """
            SELECT q.*, u.display_name, u.email, u.phone
            FROM commerce_quotes q LEFT JOIN users u ON u.id = q.user_id
            WHERE q.id = ? {}
            """.format(owner_clause),
            params,
        ).fetchone()
        if row is not None:
            result = _decode(row, 2)
        else:
            row = db.execute(
                """
                SELECT q.*, u.display_name, u.email, u.phone
                FROM quotes q LEFT JOIN users u ON u.id = q.user_id
                WHERE q.id = ? {}
                """.format(owner_clause),
                params,
            ).fetchone()
            result = _decode(row, 1)
        result = recover_quote_categories(db, result)
    if result is not None:
        result["quoted_by"] = {
            "display_name": result.get("display_name") or "",
            "email": result.get("email") or "",
            "phone": result.get("phone") or "",
        }
    return result


def find_active_quote_for_source(source_type: str, source_document_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    if source_type not in ("share", "inquiry") or not source_document_id or not user_id:
        return None
    with get_connection() as db:
        row = db.execute(
            """
            SELECT * FROM commerce_quotes
            WHERE source_type = ? AND source_document_id = ? AND user_id = ?
              AND lifecycle_status != 'archived'
            ORDER BY updated_at DESC, id DESC LIMIT 1
            """,
            (source_type, source_document_id, user_id),
        ).fetchone()
    return _decode(row, 2)


def quote_source_summaries(source_type: str, source_ids: Sequence[str], current_user_id: str) -> Dict[str, Dict[str, Any]]:
    clean_ids = list(dict.fromkeys(str(value) for value in source_ids if value))
    if source_type not in ("share", "inquiry") or not clean_ids:
        return {}
    placeholders = ",".join("?" for _ in clean_ids)
    with get_connection() as db:
        rows = db.execute(
            """
            SELECT q.id, q.source_document_id, q.user_id, q.lifecycle_status, q.updated_at,
                   COALESCE(NULLIF(u.display_name, ''), u.email, u.phone, q.user_id) AS quoted_by_name
            FROM commerce_quotes q
            JOIN users u ON u.id = q.user_id
            WHERE q.source_type = ? AND q.source_document_id IN ({})
            ORDER BY q.updated_at DESC, q.id DESC
            """.format(placeholders),
            (source_type, *clean_ids),
        ).fetchall()
    summaries: Dict[str, Dict[str, Any]] = {
        source_id: {"quote_count": 0, "historical_quote_count": 0, "quoted_by": [], "quote_links": [], "own_quote_count": 0, "own_latest_quote_id": None, "latest_quote_at": None}
        for source_id in clean_ids
    }
    seen_people: Dict[str, set] = {source_id: set() for source_id in clean_ids}
    for row in rows:
        source_id = row["source_document_id"]
        summary = summaries[source_id]
        if summary["latest_quote_at"] is None:
            summary["latest_quote_at"] = row["updated_at"]
        if row["lifecycle_status"] == "archived":
            summary["historical_quote_count"] += 1
            continue
        summary["quote_count"] += 1
        count_key = "sent_quote_count" if row["lifecycle_status"] == "sent" else "draft_quote_count"
        summary[count_key] = summary.get(count_key, 0) + 1
        summary["quote_links"].append({
            "id": row["id"],
            "user_id": row["user_id"],
            "display_name": row["quoted_by_name"],
            "lifecycle_status": row["lifecycle_status"],
            "updated_at": row["updated_at"],
            "own": row["user_id"] == current_user_id,
        })
        if row["user_id"] not in seen_people[source_id]:
            seen_people[source_id].add(row["user_id"])
            summary["quoted_by"].append({"id": row["user_id"], "display_name": row["quoted_by_name"]})
        if row["user_id"] == current_user_id:
            summary["own_quote_count"] += 1
            if summary["own_latest_quote_id"] is None:
                summary["own_latest_quote_id"] = row["id"]
    return summaries


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
    expected_version: Optional[int] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    quote = get_quote(quote_id)
    if quote is None:
        raise ValueError("Quote not found")
    document_version = int(quote.get("document_version") or 2)
    resolved_share_id = _optional_text(source_share_id or quote.get("source_share_id"), 100) or None
    clean_idempotency_key = _optional_text(idempotency_key, 80) or None
    with get_connection() as db:
        if clean_idempotency_key:
            replay = db.execute(
                "SELECT * FROM quote_deliveries WHERE delivered_by = ? AND idempotency_key = ?",
                (delivered_by, clean_idempotency_key),
            ).fetchone()
            if replay is not None:
                result = dict(replay)
                result["replayed"] = True
                return result
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
                "SELECT lifecycle_status, quote_number, version FROM commerce_quotes WHERE id = ?",
                (quote_id,),
            ).fetchone()
            if current is None:
                raise ValueError("Quote not found")
            if current["lifecycle_status"] == "archived":
                raise ValueError("Quote archived")
            if expected_version is None or int(current["version"] or 1) != int(expected_version):
                raise ValueError("Quote version conflict")
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
                    last_viewed_revision_id = NULL, notification_state = 'unread',
                    idempotency_key = ?
                WHERE id = ?
                """,
                (document_version, revision_id, resolved_share_id, delivered_by, clean_idempotency_key, delivery_id),
            )
        else:
            delivery_id = uuid.uuid4().hex
            db.execute(
                """
                INSERT INTO quote_deliveries
                    (id, quote_id, document_version, revision_id, recipient_user_id,
                     source_share_id, delivered_by, notification_state, idempotency_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'unread', ?)
                """,
                (delivery_id, quote_id, document_version, revision_id, recipient_id, resolved_share_id, delivered_by, clean_idempotency_key),
            )
        row = db.execute("SELECT * FROM quote_deliveries WHERE id = ?", (delivery_id,)).fetchone()
    result = dict(row)
    result["replayed"] = False
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
        try:
            db.execute(
                """
                UPDATE commerce_quotes
                SET lifecycle_status = ?, archived_at = NULL, archived_by = NULL,
                    version = version + 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (restored_status, quote_id),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("Quote source already exists") from error
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
        current_quote = get_quote(delivery_data["quote_id"])
        quote = get_quote_revision(revision_id) if revision_id else current_quote
        if quote is None:
            continue
        if current_quote and current_quote.get("lifecycle_status") == "archived":
            quote = _archived_customer_quote(quote, current_quote)
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
    current_quote = get_quote(quote_id)
    result = get_quote_revision(revision_id) if revision_id else current_quote
    if result is None:
        return None
    if current_quote and current_quote.get("lifecycle_status") == "archived":
        result = _archived_customer_quote(result, current_quote)
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


def _archived_customer_quote(delivered_quote: Dict[str, Any], current_quote: Dict[str, Any]) -> Dict[str, Any]:
    """Keep a customer-visible history row without exposing withdrawn pricing."""
    result = dict(delivered_quote)
    result.update({
        "lifecycle_status": "archived",
        "archived_at": current_quote.get("archived_at"),
        "updated_at": current_quote.get("updated_at") or result.get("updated_at"),
        "items": [],
        "item_count": 0,
        "total_price": 0,
        "prices_hidden": True,
    })
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


def list_reference_prices() -> Dict[str, Any]:
    with get_connection() as db:
        products = db.execute(
            "SELECT id, name, title_name, name_en, title_name_en, base_price, price_usd, sort_order FROM products WHERE enabled = 1 ORDER BY sort_order, id"
        ).fetchall()
        product_states = db.execute("SELECT id, enabled FROM products").fetchall()
        options = db.execute(
            """
            SELECT o.id, o.code, o.name, o.name_en, o.price, o.price_usd,
                   o.sort_order, c.id AS category_id, c.name AS category_name,
                   c.name_en AS category_name_en, c.catalog_type,
                   c.sort_order AS category_sort_order,
                   GROUP_CONCAT(DISTINCT po.product_id) AS product_ids
            FROM options o
            JOIN categories c ON c.id = o.category_id
            LEFT JOIN product_options po ON po.option_id = o.id AND po.enabled = 1
            WHERE o.enabled = 1 AND o.deleted_at IS NULL AND c.enabled = 1
            GROUP BY o.id, o.code, o.name, o.name_en, o.price, o.price_usd,
                     o.sort_order, c.id, c.name, c.name_en, c.catalog_type, c.sort_order
            ORDER BY CASE c.catalog_type WHEN 'optional' THEN 0 WHEN 'tools' THEN 1 WHEN 'accessories' THEN 2 ELSE 3 END,
                     c.sort_order, o.sort_order, o.id
            """
        ).fetchall()
        option_states = db.execute(
            """
            SELECT o.id, o.enabled, o.deleted_at, c.enabled AS category_enabled
            FROM options o
            LEFT JOIN categories c ON c.id = o.category_id
            """
        ).fetchall()
        base_option_states = db.execute(
            """
            SELECT o.id, o.enabled, g.enabled AS group_enabled, p.enabled AS product_enabled
            FROM product_base_options o
            JOIN product_base_option_groups g ON g.id = o.group_id
            JOIN products p ON p.id = g.product_id
            """
        ).fetchall()
    option_results = []
    for row in options:
        item = dict(row)
        item["product_ids"] = [value for value in str(item.get("product_ids") or "").split(",") if value]
        item["availability"] = "active"
        option_results.append(item)
    product_availability = {
        str(row["id"]): "active" if row["enabled"] else "inactive"
        for row in product_states
    }
    option_availability = {}
    for row in option_states:
        if row["deleted_at"]:
            status = "missing"
        elif row["enabled"] and row["category_enabled"]:
            status = "active"
        else:
            status = "inactive"
        option_availability[str(row["id"])] = status
    for row in base_option_states:
        option_availability[str(row["id"])] = (
            "active" if row["enabled"] and row["group_enabled"] and row["product_enabled"] else "inactive"
        )
    return {
        "products": [dict(row) for row in products],
        "options": option_results,
        "product_availability": product_availability,
        "option_availability": option_availability,
    }
