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
INQUIRY_STAFF_TRANSITIONS = {
    "new": {"new", "assigned", "contacted", "quoted", "closed"},
    "assigned": {"assigned", "contacted", "quoted", "closed"},
    "contacted": {"contacted", "quoted", "closed"},
    "quoted": {"quoted", "closed"},
    "closed": {"closed"},
    "cancelled": {"cancelled"},
}


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


def _document_availability(item_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = payload.get("zh") or payload.get("en") or {}
    if not isinstance(snapshot, dict) or not snapshot:
        return {"status": "snapshot_only", "details": ["SNAPSHOT_EMPTY"]}
    with get_connection() as db:
        if item_type == "device_config":
            product = snapshot.get("product") or {}
            product_id = str(product.get("id") or "").strip()
            if not product_id:
                return {"status": "snapshot_only", "details": ["PRODUCT_REFERENCE_MISSING"]}
            product_row = db.execute("SELECT enabled FROM products WHERE id = ?", (product_id,)).fetchone()
            if product_row is None:
                return {"status": "missing", "details": [product_id]}
            if not product_row["enabled"]:
                return {"status": "inactive", "details": [product_id]}
            option_ids = [
                str(option.get("id"))
                for category in snapshot.get("categories") or []
                for option in category.get("options") or []
                if option.get("id")
            ]
            if option_ids:
                placeholders = ",".join("?" for _ in option_ids)
                option_rows = db.execute(
                    """
                    SELECT o.id, o.enabled, o.deleted_at, c.enabled AS category_enabled
                    FROM options o LEFT JOIN categories c ON c.id = o.category_id
                    WHERE o.id IN ({})
                    """.format(placeholders),
                    option_ids,
                ).fetchall()
                base_rows = db.execute(
                    """
                    SELECT o.id, o.enabled, NULL AS deleted_at, g.enabled AS category_enabled
                    FROM product_base_options o
                    JOIN product_base_option_groups g ON g.id = o.group_id
                    WHERE g.product_id = ? AND o.id IN ({})
                    """.format(placeholders),
                    (product_id, *option_ids),
                ).fetchall()
                found = {str(row["id"]): row for row in [*option_rows, *base_rows]}
                missing = [option_id for option_id in option_ids if option_id not in found or found[option_id]["deleted_at"]]
                if missing:
                    return {"status": "missing", "details": missing}
                inactive = [option_id for option_id in option_ids if not found[option_id]["enabled"] or not found[option_id]["category_enabled"]]
                if inactive:
                    return {"status": "inactive", "details": inactive}
            color_code = str((snapshot.get("color") or {}).get("code") or "").strip()
            if not color_code:
                return {"status": "snapshot_only", "details": ["COLOR_REFERENCE_MISSING"]}
            selections = {}
            for category in snapshot.get("categories") or []:
                selected = [option.get("id") for option in category.get("options") or [] if option.get("id")]
                if selected:
                    selections[category.get("id")] = selected if category.get("multiple") else selected[0]
            try:
                build_snapshot(product_id, color_code, selections, "zh")
            except (ValueError, TypeError, KeyError):
                return {"status": "snapshot_only", "details": ["SELECTION_RULES_CHANGED"]}
            return {"status": "active", "details": []}

        option_id = str(snapshot.get("option_id") or "").strip()
        if not option_id:
            return {"status": "snapshot_only", "details": ["CATALOG_REFERENCE_MISSING"]}
        row = db.execute(
            """
            SELECT o.enabled, o.deleted_at, c.enabled AS category_enabled, c.catalog_type
            FROM options o LEFT JOIN categories c ON c.id = o.category_id
            WHERE o.id = ?
            """,
            (option_id,),
        ).fetchone()
        if row is None or row["deleted_at"]:
            return {"status": "missing", "details": [option_id]}
        expected_type = "tools" if item_type == "tool" else "accessories"
        if row["catalog_type"] != expected_type:
            return {"status": "missing", "details": [option_id]}
        if not row["enabled"] or not row["category_enabled"]:
            return {"status": "inactive", "details": [option_id]}
    return {"status": "active", "details": []}


def _bounded_provenance(item: Dict[str, Any]) -> Dict[str, Any]:
    remaining = max(1, int(item.get("quantity") or 1))
    sources = []
    for raw in item.get("source_trace") or []:
        if not isinstance(raw, dict) or remaining <= 0:
            continue
        source_id = str(raw.get("source_share_id") or "").strip()
        source_code = str(raw.get("source_share_code") or "").strip()
        if not source_id and not source_code:
            continue
        quantity = min(remaining, max(1, int(raw.get("imported_quantity") or 1)))
        remaining -= quantity
        sources.append({
            "source_key": str(raw.get("source_key") or "{}:{}".format(int(raw.get("source_document_version") or 1), source_id or source_code)),
            "source_share_id": source_id,
            "source_share_code": source_code,
            "source_document_version": int(raw.get("source_document_version") or 1),
            "source_item_id": str(raw.get("source_item_id") or ""),
            "quantity": quantity,
        })
    return {"sources": sources, "manual_quantity": remaining}


def _decode_item(row, language: str) -> Dict[str, Any]:
    item = dict(row)
    payload = json.loads(item.pop("snapshot_json"))
    item["snapshot"] = payload.get("en" if language == "en" else "zh") or {}
    item["provenance"] = payload.get("provenance") or {"sources": [], "manual_quantity": int(item.get("quantity") or 1)}
    captured = payload.get("availability") or {"status": "snapshot_only", "details": ["CAPTURE_STATUS_UNAVAILABLE"]}
    current = _document_availability(str(item.get("item_type") or ""), payload)
    item["captured_availability"] = str(captured.get("status") or "snapshot_only")
    item["captured_availability_details"] = captured.get("details") or []
    item["availability"] = str(current.get("status") or "snapshot_only")
    item["availability_details"] = current.get("details") or []
    return item


def _decode_inquiry(row, item_rows, source_rows, language: str) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    result = dict(row)
    result["items"] = [_decode_item(item, language) for item in item_rows]
    result["sources"] = [dict(source) for source in source_rows]
    result["source_count"] = len(result["sources"])
    result["source_codes"] = [source["source_share_code"] for source in result["sources"] if source["source_share_code"]]
    result["manual_item_count"] = sum(1 for item in result["items"] if int((item.get("provenance") or {}).get("manual_quantity") or 0) > 0)
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
                   creator.address AS customer_address_current,
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
        sources = db.execute(
            "SELECT source_key, source_share_id, source_share_code, source_document_version, item_count, quantity, created_at FROM customer_inquiry_sources WHERE inquiry_id = ? ORDER BY created_at, id",
            (inquiry_id,),
        ).fetchall()
    return _decode_inquiry(row, items, sources, selected_language)


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
    prepared_items = []
    source_totals: Dict[str, Dict[str, Any]] = {}
    for item in loaded_items:
        provenance = _bounded_provenance(item)
        availability = _document_availability(str(item.get("item_type") or ""), item.get("payload") or {})
        payload = dict(item.get("payload") or {})
        payload["provenance"] = provenance
        payload["availability"] = availability
        prepared_items.append({**item, "payload": payload})
        for source in provenance["sources"]:
            key = source["source_key"]
            record = source_totals.setdefault(key, {
                "source_key": key,
                "source_share_id": source["source_share_id"],
                "source_share_code": source["source_share_code"],
                "source_document_version": source["source_document_version"],
                "item_count": 0,
                "quantity": 0,
            })
            record["item_count"] += 1
            record["quantity"] += int(source["quantity"])

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
                customer["phone_country"] or "", _clean_message(message), len(prepared_items), idempotency_key,
            ),
        )
        for index, item in enumerate(prepared_items):
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
        for source in source_totals.values():
            db.execute(
                """
                INSERT INTO customer_inquiry_sources
                    (id, inquiry_id, source_key, source_share_id, source_share_code,
                     source_document_version, item_count, quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex, inquiry_id, source["source_key"], source["source_share_id"] or None,
                    source["source_share_code"], source["source_document_version"], source["item_count"], source["quantity"],
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
    with get_connection() as db:
        product_row = db.execute("SELECT enabled FROM products WHERE id = ?", (product_id,)).fetchone()
    if product_row is None:
        raise InquiryError("INQUIRY_PRODUCT_NOT_FOUND")
    if not product_row["enabled"]:
        raise InquiryError("INQUIRY_PRODUCT_INACTIVE")
    try:
        zh = build_snapshot(product_id, color, selections, "zh")
        en = build_snapshot(product_id, color, selections, "en")
    except ValueError as error:
        detail = str(error)
        if detail == "Product not found":
            raise InquiryError("INQUIRY_PRODUCT_NOT_FOUND")
        if detail == "Unsupported product color":
            raise InquiryError("INQUIRY_COLOR_UNAVAILABLE")
        if detail.startswith("Unsupported option:"):
            raise InquiryError("INQUIRY_OPTION_UNAVAILABLE")
        raise InquiryError("INQUIRY_CONFIGURATION_INVALID")
    except (TypeError, KeyError):
        raise InquiryError("INQUIRY_CONFIGURATION_INVALID")
    product = zh.get("product") or {}
    document = {
        "item_type": "device_config",
        "source_id": None,
        "quantity": 1,
        "display_name": product.get("name") or product.get("title_name") or "",
        "payload": {"zh": zh, "en": en},
        "source_trace": [],
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
    except CatalogValidationError as error:
        if error.code in ("CONFIG_ACCESS_DENIED", "CATALOG_CART_ITEM_NOT_FOUND"):
            raise InquiryError("INQUIRY_CART_ITEM_UNAVAILABLE")
        raise InquiryError("INQUIRY_CONFIGURATION_INVALID")
    return sorted(loaded, key=_canonical_cart_order)


def create_cart_inquiry(user_id: str, language: str, message: str, idempotency_key: str) -> Dict[str, Any]:
    loaded = _cart_loaded_items(user_id)
    return _insert_inquiry(user_id, "cart", loaded, language, message, idempotency_key)


def list_customer_inquiries(user_id: str, page: int = 1, page_size: int = 20, query: str = "", status: str = "", hidden: bool = False) -> Dict[str, Any]:
    safe_page = max(int(page), 1)
    safe_size = min(max(int(page_size), 1), 50)
    with get_connection() as db:
        where = """created_by=? AND COALESCE((SELECT hidden FROM personal_business_visibility v WHERE v.user_id=? AND v.resource_type='inquiries' AND v.resource_id=i.id),0)=?
            AND (?='' OR instr(lower(inquiry_number),lower(?))>0) AND (?='' OR status=?)"""
        params = (user_id, user_id, int(hidden), query, query, status, status)
        total = int(db.execute(f"SELECT COUNT(*) FROM customer_inquiries i WHERE {where}", params).fetchone()[0])
        safe_page = min(safe_page, max(1, (total + safe_size - 1) // safe_size))
        rows = db.execute(
            f"SELECT i.* FROM customer_inquiries i WHERE {where} ORDER BY created_at DESC,id LIMIT ? OFFSET ?",
            (*params, safe_size, (safe_page - 1) * safe_size),
        ).fetchall()
    return {"items": [dict(row, hidden=hidden) for row in rows], "total": total, "page": safe_page, "page_size": safe_size}


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
    # Shares and inquiries form the common sales opportunity pool.  Every
    # enabled sales/admin account may discover and inspect every inquiry; the
    # assignee still controls who may mutate its workflow fields.
    return "", ()


def _staff_can_read(inquiry: Optional[Dict[str, Any]]) -> bool:
    return bool(inquiry)


def _staff_can_manage(inquiry: Optional[Dict[str, Any]], actor_id: str, actor_role: str) -> bool:
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
    business_states = {"new", "assigned", "contacted", "pending", "sent", "archived", "closed", "cancelled"}
    is_business = selected_status.startswith("business_")
    if selected_status != "all" and selected_status not in INQUIRY_STATES and not (is_business and selected_status[9:] in business_states):
        raise InquiryError("INQUIRY_STATUS_CONFLICT")
    business_sql = """CASE WHEN i.status IN ('closed','cancelled') THEN i.status
        WHEN EXISTS (SELECT 1 FROM commerce_quotes q WHERE q.source_type='inquiry' AND q.source_document_id=i.id AND q.lifecycle_status='sent') THEN 'sent'
        WHEN EXISTS (SELECT 1 FROM commerce_quotes q WHERE q.source_type='inquiry' AND q.source_document_id=i.id AND q.lifecycle_status='draft') THEN 'pending'
        WHEN EXISTS (SELECT 1 FROM commerce_quotes q WHERE q.source_type='inquiry' AND q.source_document_id=i.id AND q.lifecycle_status='archived') THEN 'archived'
        WHEN i.status='quoted' THEN 'pending' ELSE i.status END"""
    like = "%{}%".format(str(query or "").strip())
    scope, scope_params = _staff_scope_clause(actor_id, actor_role)
    filters = """
        FROM customer_inquiries i
        JOIN users creator ON creator.id = i.created_by
        LEFT JOIN users assignee ON assignee.id = i.assigned_to
        WHERE 1 = 1 {}
          AND (? = 'all' OR i.status = ?)
          AND (? = '%' OR i.inquiry_number LIKE ? OR creator.display_name LIKE ?
               OR creator.email LIKE ? OR creator.phone LIKE ? OR i.customer_name_snapshot LIKE ?
               OR EXISTS (
                   SELECT 1 FROM customer_inquiry_sources cis
                   WHERE cis.inquiry_id = i.id AND cis.source_share_code LIKE ?
               ))
    """.format(scope)
    if is_business:
        filters = filters.replace("i.status = ?", "(" + business_sql + ") = ?")
    params = (*scope_params, selected_status, selected_status[9:] if is_business else selected_status, like, like, like, like, like, like, like)
    with get_connection() as db:
        total = int(db.execute("SELECT COUNT(*) " + filters, params).fetchone()[0])
        rows = db.execute(
            """
            SELECT i.*, creator.display_name AS customer_display_name,
                   creator.email AS customer_email_current, creator.phone AS customer_phone_current,
                   assignee.display_name AS assignee_name,
            """ + business_sql + " AS business_status " + filters + " ORDER BY CASE i.status WHEN 'new' THEN 0 WHEN 'assigned' THEN 1 ELSE 2 END, i.created_at DESC LIMIT ? OFFSET ?",
            (*params, safe_size, (safe_page - 1) * safe_size),
        ).fetchall()
        inquiry_ids = [row["id"] for row in rows]
        item_summaries: Dict[str, List[Dict[str, Any]]] = {inquiry_id: [] for inquiry_id in inquiry_ids}
        source_summaries: Dict[str, List[Dict[str, Any]]] = {inquiry_id: [] for inquiry_id in inquiry_ids}
        manual_counts: Dict[str, int] = {inquiry_id: 0 for inquiry_id in inquiry_ids}
        if inquiry_ids:
            placeholders = ",".join("?" for _ in inquiry_ids)
            count_rows = db.execute(
                "SELECT inquiry_id, item_type, COUNT(*) AS item_count, COALESCE(SUM(quantity), 0) AS quantity FROM customer_inquiry_items WHERE inquiry_id IN ({}) GROUP BY inquiry_id, item_type".format(placeholders),
                inquiry_ids,
            ).fetchall()
            for count in count_rows:
                item_summaries[count["inquiry_id"]].append({key: count[key] for key in ("item_type", "item_count", "quantity")})
            source_rows = db.execute(
                "SELECT inquiry_id, source_share_id, source_share_code, source_document_version, item_count, quantity FROM customer_inquiry_sources WHERE inquiry_id IN ({}) ORDER BY created_at, id".format(placeholders),
                inquiry_ids,
            ).fetchall()
            for source in source_rows:
                source_summaries[source["inquiry_id"]].append({key: source[key] for key in ("source_share_id", "source_share_code", "source_document_version", "item_count", "quantity")})
            provenance_rows = db.execute(
                "SELECT inquiry_id, snapshot_json FROM customer_inquiry_items WHERE inquiry_id IN ({})".format(placeholders),
                inquiry_ids,
            ).fetchall()
            for provenance_row in provenance_rows:
                try:
                    stored = json.loads(provenance_row["snapshot_json"]) or {}
                    provenance = stored.get("provenance")
                except (TypeError, ValueError, json.JSONDecodeError):
                    provenance = None
                if provenance is None or int(provenance.get("manual_quantity") or 0) > 0:
                    manual_counts[provenance_row["inquiry_id"]] += 1
        results = []
        for row in rows:
            record = dict(row)
            record["item_summary"] = item_summaries.get(record["id"], [])
            record["sources"] = source_summaries.get(record["id"], [])
            record["source_count"] = len(record["sources"])
            record["source_codes"] = [source["source_share_code"] for source in record["sources"] if source["source_share_code"]]
            record["manual_item_count"] = manual_counts.get(record["id"], 0)
            results.append(record)
    return {"items": results, "total": total, "page": safe_page, "page_size": safe_size, "language": selected_language}


def get_staff_inquiry(inquiry_id: str, actor_id: str, actor_role: str, language: str = "zh") -> Optional[Dict[str, Any]]:
    inquiry = _load_inquiry(inquiry_id, language)
    return inquiry if _staff_can_read(inquiry) else None


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
    if not _staff_can_manage(inquiry, actor_id, actor_role):
        raise InquiryError("INQUIRY_ACCESS_DENIED")
    if int(inquiry.get("version") or 0) != int(version):
        raise InquiryError("INQUIRY_STATUS_CONFLICT")
    target_status = str(status or inquiry["status"])
    if target_status not in INQUIRY_STATES or target_status == "cancelled":
        raise InquiryError("INQUIRY_STATUS_CONFLICT")
    if target_status not in INQUIRY_STAFF_TRANSITIONS.get(str(inquiry.get("status") or ""), set()):
        raise InquiryError("INQUIRY_STATUS_TRANSITION_INVALID")
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
    if target_status in ("assigned", "contacted", "quoted") and not target_assignee:
        target_assignee = actor_id
    if target_status == "new" and target_assignee:
        target_status = "assigned"
    closed_at = "CURRENT_TIMESTAMP" if target_status in ("closed", "cancelled") else "NULL"
    with get_connection() as db:
        cursor = db.execute(
            """
            UPDATE customer_inquiries
            SET status = ?, assigned_to = ?,
                assigned_at = CASE WHEN ? IS NOT NULL THEN COALESCE(assigned_at, CURRENT_TIMESTAMP) ELSE assigned_at END,
                contacted_at = CASE WHEN ? = 'contacted' THEN COALESCE(contacted_at, CURRENT_TIMESTAMP) ELSE contacted_at END,
                closed_at = {}, version = version + 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND version = ?
            """.format(closed_at),
            (target_status, target_assignee or None, target_assignee or None, target_status, inquiry_id, version),
        )
    if not cursor.rowcount:
        raise InquiryError("INQUIRY_STATUS_CONFLICT")
    return _load_inquiry(inquiry_id, "zh")


def inquiry_quote_items(inquiry: Dict[str, Any], currency: str = "CNY") -> List[Dict[str, Any]]:
    """Flatten an immutable inquiry snapshot into price-editable quote rows.

    Device base prices and catalog reference prices come from the immutable
    inquiry snapshot.  Motor and channel choices describe the device base line,
    while power remains a locked surcharge line.  Sales can still override the
    resulting commercial price without mutating the inquiry snapshot.
    """
    rows: List[Dict[str, Any]] = []
    selected_currency = "USD" if str(currency).upper() == "USD" else "CNY"
    device_index = 0
    for entry in inquiry.get("items") or []:
        snapshot = entry.get("snapshot") or {}
        item_type = str(entry.get("item_type") or "device_config")
        availability = str(entry.get("availability") or "snapshot_only")
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
                "availability": availability,
                "captured_availability": entry.get("captured_availability") or availability,
                "availability_details": entry.get("availability_details") or [],
            })
            continue
        device_index += 1
        product = snapshot.get("product") or {}
        label = "Device {} · {}".format(device_index, product.get("name") or product.get("id") or "—")
        specifications = []
        color = snapshot.get("color") or {}
        if color.get("label") or color.get("code"):
            specifications.append({
                "key": "color",
                "label": "Appearance" if selected_currency == "USD" else "外观颜色",
                "value": color.get("label") or color.get("code"),
            })
        for category in snapshot.get("categories") or []:
            category_id = str(category.get("id") or "").strip().lower()
            if category_id not in {"motor", "channel", "voltage", "power"}:
                continue
            names = [str(option.get("name") or option.get("code") or "").strip() for option in category.get("options") or []]
            names = [name for name in names if name]
            if names:
                specifications.append({
                    "key": category_id,
                    "label": category.get("name") or category_id,
                    "value": " / ".join(names),
                })
        base_cny = product.get("base_price") or 0
        base_usd = product.get("price_usd") or 0
        base_price = base_usd if selected_currency == "USD" else base_cny
        rows.append({
            "kind": "product", "source_id": product.get("id"),
            "name": product.get("title_name") or product.get("name") or "Device",
            "device_label": label, "code": product.get("name") or product.get("id") or "",
            "quantity": 1, "price": base_price, "price_cny": base_cny, "price_usd": base_usd,
            "reference_price": base_price, "locked": True,
            "configuration_role": "base_device", "device_specifications": specifications,
            "availability": availability,
            "captured_availability": entry.get("captured_availability") or availability,
            "availability_details": entry.get("availability_details") or [],
        })
        for category_index, category in enumerate(snapshot.get("categories") or []):
            category_id = str(category.get("id") or "").strip().lower()
            for option_index, option in enumerate(category.get("options") or []):
                base_option_type = str(option.get("base_option_type") or "").strip().lower()
                if category_id in {"motor", "channel"} or base_option_type in {"motor", "channel"}:
                    continue
                price_cny = option.get("price_cny") or option.get("price") or 0
                price_usd = option.get("price_usd") or 0
                selected_price = price_usd if selected_currency == "USD" else price_cny
                is_power = category_id in {"voltage", "power"} or base_option_type == "power"
                rows.append({
                    "kind": "surcharge" if is_power else "option",
                    "source_id": option.get("id"), "name": option.get("name") or "Option",
                    "device_label": label, "code": option.get("code") or "", "quantity": 1,
                    "price": selected_price, "price_cny": price_cny, "price_usd": price_usd,
                    "reference_price": selected_price, "category_id": category_id,
                    "category_name": category.get("name") or "",
                    "category_name_en": category.get("name_en") or "",
                    "category_sort_order": -1 if is_power else category.get("sort_order", category_index),
                    "sort_order": option.get("sort_order", option_index),
                    "locked": is_power, "configuration_role": "base_power" if is_power else "optional",
                    "availability": availability,
                    "captured_availability": entry.get("captured_availability") or availability,
                    "availability_details": entry.get("availability_details") or [],
                })
    if not rows:
        raise InquiryError("INQUIRY_SNAPSHOT_INVALID")
    return rows


def mark_inquiry_quoted(inquiry_id: str, actor_id: str, actor_role: str, quote_id: str, version: int) -> Optional[Dict[str, Any]]:
    inquiry = _load_inquiry(inquiry_id, "zh")
    if inquiry is None:
        return None
    if not _staff_can_read(inquiry):
        raise InquiryError("INQUIRY_ACCESS_DENIED")
    # A source may legitimately be quoted by more than one salesperson.  The
    # legacy converted_quote_id remains the immutable first-quote pointer; the
    # quote source table is authoritative for all later quotations.
    already_quoted = bool(inquiry.get("converted_quote_id"))
    if int(inquiry.get("version") or 0) != int(version) and not already_quoted:
        raise InquiryError("INQUIRY_STATUS_CONFLICT")
    with get_connection() as db:
        if already_quoted:
            cursor = db.execute(
                """
                UPDATE customer_inquiries
                SET status = 'quoted', quoted_at = COALESCE(quoted_at, CURRENT_TIMESTAMP),
                    assigned_to = COALESCE(assigned_to, ?),
                    assigned_at = COALESCE(assigned_at, CURRENT_TIMESTAMP),
                    latest_quoted_at = CURRENT_TIMESTAMP,
                    version = version + 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (actor_id, inquiry_id),
            )
        else:
            cursor = db.execute(
                """
                UPDATE customer_inquiries
                SET converted_quote_id = ?, status = 'quoted',
                    assigned_to = COALESCE(assigned_to, ?),
                    assigned_at = COALESCE(assigned_at, CURRENT_TIMESTAMP),
                    quoted_at = COALESCE(quoted_at, CURRENT_TIMESTAMP),
                    first_quoted_at = COALESCE(first_quoted_at, CURRENT_TIMESTAMP),
                    latest_quoted_at = CURRENT_TIMESTAMP,
                    version = version + 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND version = ? AND converted_quote_id IS NULL
                """,
                (quote_id, actor_id, inquiry_id, version),
            )
    if not cursor.rowcount:
        raise InquiryError("INQUIRY_STATUS_CONFLICT")
    result = _load_inquiry(inquiry_id, "zh")
    if result is not None:
        result["replayed"] = already_quoted
    return result
