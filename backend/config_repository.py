import json
import secrets
import sqlite3
import uuid
from copy import deepcopy
from datetime import timedelta
from typing import Any, Dict, List, Optional

from .database import get_connection
from .repository import get_product, get_public_product_snapshot
from .pricing_service import calculate_product_price
from .security import to_iso, utc_now


SHARE_DAYS = 90


def _build_legacy_snapshot(product_id: str, color: str, selections: Dict[str, Any], lang: str = "zh") -> Dict[str, Any]:
    product = get_product(product_id, "en" if lang == "en" else "zh")
    if product is None:
        raise ValueError("Product not found")

    colors = {item["code"]: item for item in product["colors"]}
    if color not in colors:
        raise ValueError("Unsupported product color")

    snapshot: Dict[str, Any] = {
        "product": {
            "id": product["id"],
            "name": product["name"],
            "title_name": product["title_name"],
            "description": product.get("description", ""),
            "base_price": product.get("base_price", 0),
            "price_usd": product.get("price_usd", 0),
        },
        "color": colors[color],
        "categories": [],
    }

    for category in product["categories"]:
        requested = selections.get(category["id"])
        requested_ids = requested if isinstance(requested, list) else [requested] if requested else []
        option_map = {option["id"]: option for option in category["options"]}
        if category["id"] == "motor" and not requested_ids and option_map:
            # Preserve existing saved-config/quote callers while keeping motor single-select.
            requested_ids = [next(iter(option_map))]
        invalid = [option_id for option_id in requested_ids if option_id not in option_map]
        if invalid:
            raise ValueError("Unsupported option: " + ", ".join(invalid))
        if not category["multiple"] and len(requested_ids) > 1:
            raise ValueError("Only one option may be selected for " + category["id"])
        if requested_ids:
            snapshot["categories"].append(
                {
                    "id": category["id"],
                    "name": category["name"],
                    "multiple": category["multiple"],
                    "options": [option_map[option_id] for option_id in requested_ids],
                }
            )
    motor_category = next((category for category in snapshot["categories"] if category["id"] == "motor"), None)
    if not motor_category or len(motor_category["options"]) != 1:
        raise ValueError("Exactly one motor option is required")
    motor = motor_category["options"][0]
    if motor.get("motor_base_price_cny") is None or motor.get("motor_base_price_usd") is None:
        raise ValueError("Selected motor does not have CNY and USD base prices")
    snapshot["product"]["base_price"] = motor["motor_base_price_cny"]
    snapshot["product"]["price_usd"] = motor["motor_base_price_usd"]
    snapshot["product"]["motor_option_id"] = motor.get("id")
    return snapshot


def _build_v2_snapshot(product: Dict[str, Any], color: str, selections: Dict[str, Any], lang: str) -> Dict[str, Any]:
    colors = {item["code"]: item for item in product["colors"]}
    if color not in colors:
        raise ValueError("Unsupported product color")

    categories = []
    selected_base: Dict[str, Optional[str]] = {"motor": None, "channel": None, "power": None}
    for group in product.get("base_option_groups") or []:
        category_id = "voltage" if group["type"] == "power" else group["type"]
        option_map = {option["id"]: option for option in group.get("options") or []}
        requested = selections.get(category_id)
        requested_id = requested[0] if isinstance(requested, list) and requested else requested
        if not requested_id and group.get("required") and option_map:
            requested_id = next(iter(option_map))
        if requested_id and requested_id not in option_map:
            raise ValueError("Unsupported option: {}".format(requested_id))
        if not requested_id:
            continue
        option = option_map[requested_id]
        selected_base[group["type"]] = requested_id
        categories.append(
            {
                "id": category_id,
                "name": group["name"],
                "multiple": False,
                "options": [
                    {
                        "id": option["id"],
                        "name": option["name"],
                        "description": "",
                        "special_note": "",
                        "price": float(option["price_usd"] if lang == "en" else option["price_cny"]),
                        "price_cny": option["price_cny"],
                        "price_usd": option["price_usd"],
                        "price_confirmed": option["price_confirmed"],
                        "is_free": option["is_free"],
                        "base_option_type": group["type"],
                    }
                ],
            }
        )

    optional_ids: List[str] = []
    for category in product.get("optional_categories") or []:
        option_map = {option["id"]: option for option in category.get("options") or []}
        requested = selections.get(category["id"])
        requested_ids = requested if isinstance(requested, list) else [requested] if requested else []
        invalid = [option_id for option_id in requested_ids if option_id not in option_map]
        if invalid:
            raise ValueError("Unsupported option: " + ", ".join(invalid))
        if not requested_ids:
            continue
        optional_ids.extend(requested_ids)
        category_options = []
        for option_id in requested_ids:
            option = option_map[option_id]
            category_options.append(
                {
                    "id": option["id"],
                    "code": option["code"],
                    "name": option["name"],
                    "description": option["description"],
                    "note": option["note"],
                    "special_note": option.get("special_note") or "",
                    "image_path": (option.get("image") or {}).get("path"),
                    "image_width": (option.get("image") or {}).get("width"),
                    "image_height": (option.get("image") or {}).get("height"),
                    "price": float(option["price_usd"] if lang == "en" else option["price_cny"]),
                    "price_cny": option["price_cny"],
                    "price_usd": option["price_usd"],
                    "price_confirmed": option["price_confirmed"],
                    "mapping_id": option.get("mapping_id"),
                }
            )
        categories.append(
            {
                "id": category["id"],
                "name": category["name"],
                "multiple": True,
                "options": category_options,
            }
        )

    pricing = calculate_product_price(
        product["id"],
        motor_option_id=selected_base["motor"],
        channel_option_id=selected_base["channel"],
        power_option_id=selected_base["power"],
        optional_config_ids=optional_ids,
        currency="USD" if lang == "en" else "CNY",
        language=lang,
    )
    color_item = colors[color]
    return {
        "schema_version": 2,
        "language": lang,
        "product": {
            "id": product["id"],
            "name": product["model"],
            "title_name": product["name"],
            "description": product.get("overview", ""),
            "base_price": float(pricing["base_price"]) if lang != "en" else 0,
            "price_usd": float(pricing["base_price"]) if lang == "en" else 0,
            "motor_option_id": selected_base["motor"],
            "channel_option_id": selected_base["channel"],
            "price_variant_id": next((line["source_id"] for line in pricing["lines"] if line["kind"] == "base_price"), None),
        },
        "color": {
            "code": color_item["code"],
            "label": color_item["name"],
            "display_color": color_item.get("display_color"),
            "image_path": (color_item.get("image") or {}).get("path"),
            "image_width": (color_item.get("image") or {}).get("width"),
            "image_height": (color_item.get("image") or {}).get("height"),
        },
        "categories": categories,
        "pricing": pricing,
    }


def build_snapshot(product_id: str, color: str, selections: Dict[str, Any], lang: str = "zh") -> Dict[str, Any]:
    language = "en" if lang == "en" else "zh"
    product = get_public_product_snapshot(product_id, language)
    if product is not None and product.get("base_option_groups"):
        return _build_v2_snapshot(product, color, selections, language)
    return _build_legacy_snapshot(product_id, color, selections, language)


def save_config(user_id: str, name: str, product_id: str, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    config_id = uuid.uuid4().hex
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO saved_configs (id, user_id, name, product_id, snapshot_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (config_id, user_id, name.strip() or snapshot["product"]["name"], product_id, json.dumps(snapshot, ensure_ascii=False)),
        )
    return get_saved_config(config_id, user_id)  # type: ignore


def _refresh_snapshot(snapshot: Dict[str, Any], lang: str) -> Dict[str, Any]:
    """Rebuild catalog text from current data while preserving saved selections."""
    product = snapshot.get("product") or {}
    color = snapshot.get("color") or {}
    product_id = product.get("id")
    color_code = color.get("code")
    if not product_id or not color_code:
        return snapshot

    selections: Dict[str, Any] = {}
    for category in snapshot.get("categories") or []:
        option_ids = [option.get("id") for option in category.get("options") or [] if option.get("id")]
        if option_ids:
            selections[category["id"]] = option_ids if category.get("multiple") else option_ids[0]
    try:
        return build_snapshot(product_id, color_code, selections, lang)
    except ValueError:
        # Keep historical data readable if a formerly selected catalog item was removed.
        return snapshot


def _decode(row: Any, lang: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    item = dict(row)
    item["snapshot"] = json.loads(item.pop("snapshot_json"))
    if lang in ("zh", "en"):
        item["snapshot"] = _refresh_snapshot(deepcopy(item["snapshot"]), lang)
    return item


def get_saved_config(config_id: str, user_id: Optional[str] = None, lang: Optional[str] = None) -> Optional[Dict[str, Any]]:
    query = "SELECT * FROM saved_configs WHERE id = ?"
    params: List[Any] = [config_id]
    if user_id:
        query += " AND user_id = ? AND archived_at IS NULL"
        params.append(user_id)
    with get_connection() as connection:
        row = connection.execute(query, params).fetchone()
    return _decode(row, lang)


def list_saved_configs(user_id: str, lang: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM saved_configs WHERE user_id = ? AND archived_at IS NULL ORDER BY created_at ASC, id ASC", (user_id,)
        ).fetchall()
    return [_decode(row, lang) for row in rows]  # type: ignore


def delete_saved_config(config_id: str, user_id: str) -> bool:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE saved_configs
            SET archived_at = CURRENT_TIMESTAMP, status = 'closed', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ? AND archived_at IS NULL
            """,
            (config_id, user_id),
        )
    return cursor.rowcount > 0


def update_saved_config(config_id: str, user_id: str, name: str, product_id: str, snapshot: Dict[str, Any], version: int) -> Optional[Dict[str, Any]]:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE saved_configs
            SET name = ?, product_id = ?, snapshot_json = ?, version = version + 1,
                status = 'draft', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ? AND archived_at IS NULL AND version = ?
            """,
            (name.strip() or snapshot["product"]["name"], product_id, json.dumps(snapshot, ensure_ascii=False), config_id, user_id, version),
        )
        if cursor.rowcount == 0:
            return None
    return get_saved_config(config_id, user_id)


def archive_saved_configs(config_ids: List[str], user_id: str) -> int:
    unique_ids = list(dict.fromkeys(config_ids))
    if not unique_ids:
        return 0
    placeholders = ",".join("?" for _ in unique_ids)
    with get_connection() as connection:
        owned = connection.execute(
            "SELECT id FROM saved_configs WHERE user_id = ? AND archived_at IS NULL AND id IN ({})".format(placeholders),
            [user_id] + unique_ids,
        ).fetchall()
        if len(owned) != len(unique_ids):
            raise ValueError("CONFIG_ACCESS_DENIED")
        cursor = connection.execute(
            "UPDATE saved_configs SET archived_at = CURRENT_TIMESTAMP, status = 'closed', updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND id IN ({})".format(placeholders),
            [user_id] + unique_ids,
        )
    return cursor.rowcount


def create_share(config_id: str, user_id: str) -> Dict[str, Any]:
    return create_share_bundle([config_id], user_id, "zh")


def create_share_bundle(config_ids: List[str], user_id: str, lang: str = "zh") -> Dict[str, Any]:
    unique_ids = list(dict.fromkeys(config_ids))
    if not 1 <= len(unique_ids) <= 20:
        raise ValueError("BATCH_SELECTION_LIMIT" if unique_ids else "BATCH_SELECTION_EMPTY")
    configs = [get_saved_config(config_id, user_id) for config_id in unique_ids]
    if any(config is None for config in configs):
        raise ValueError("CONFIG_ACCESS_DENIED")

    selected_lang = "en" if lang == "en" else "zh"
    expires_at = to_iso(utc_now() + timedelta(days=SHARE_DAYS))
    share_id = uuid.uuid4().hex
    with get_connection() as connection:
        user = connection.execute("SELECT display_name, email, phone FROM users WHERE id = ?", (user_id,)).fetchone()
        customer_name = (user["display_name"] if user else "") or ""
        customer_email = ((user["email"] or user["phone"]) if user else "") or ""
        code = None
        for _ in range(20):
            candidate = "{:06d}".format(secrets.randbelow(1000000))
            connection.execute("SAVEPOINT share_code_allocation")
            try:
                connection.execute(
                    """
                    INSERT INTO config_shares
                    (id, config_id, code, created_by, expires_at, title, language, customer_name, customer_email, item_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (share_id, unique_ids[0], candidate, user_id, expires_at, "Configuration" if selected_lang == "en" else "设备配置", selected_lang, customer_name, customer_email, len(unique_ids)),
                )
                connection.execute("RELEASE SAVEPOINT share_code_allocation")
                code = candidate
                break
            except sqlite3.IntegrityError:
                connection.execute("ROLLBACK TO SAVEPOINT share_code_allocation")
                connection.execute("RELEASE SAVEPOINT share_code_allocation")
                continue
        if code is None:
            raise RuntimeError("Unable to allocate a share code")
        for index, config in enumerate(configs):
            raw_snapshot = config["snapshot"]
            bilingual_snapshot = {
                "zh": _refresh_snapshot(deepcopy(raw_snapshot), "zh"),
                "en": _refresh_snapshot(deepcopy(raw_snapshot), "en"),
            }
            connection.execute(
                """
                INSERT INTO config_share_items
                (id, share_id, config_id, sort_order, display_name, snapshot_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (uuid.uuid4().hex, share_id, config["id"], index, config["name"], json.dumps(bilingual_snapshot, ensure_ascii=False)),
            )
        placeholders = ",".join("?" for _ in unique_ids)
        connection.execute(
            "UPDATE saved_configs SET status = 'shared', updated_at = CURRENT_TIMESTAMP WHERE id IN ({})".format(placeholders),
            unique_ids,
        )
        return {"id": share_id, "code": code, "config_id": unique_ids[0], "item_count": len(unique_ids), "expires_at": expires_at}


def get_share(code: str, lang: Optional[str] = None, increment_view: bool = True) -> Optional[Dict[str, Any]]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT s.id, s.code, s.config_id, s.expires_at, s.view_count, s.created_at,
                   s.title, s.language, s.customer_name, s.customer_email, s.item_count,
                   c.name, c.product_id,
                   u.display_name AS sender_name, u.email AS sender_email, u.phone AS sender_phone
            FROM config_shares s
            JOIN saved_configs c ON c.id = s.config_id
            JOIN users u ON u.id = c.user_id
            WHERE s.code = ? AND s.active = 1 AND s.expires_at > ?
            """,
            (code, to_iso(utc_now())),
        ).fetchone()
        if row is None:
            return None
        if increment_view:
            connection.execute(
                """
                UPDATE config_shares
                SET view_count = view_count + 1, last_viewed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (row["id"],),
            )
        share_items = connection.execute(
            "SELECT id, config_id, sort_order, display_name, snapshot_json FROM config_share_items WHERE share_id = ? ORDER BY sort_order, created_at",
            (row["id"],),
        ).fetchall()
    item = dict(row)
    selected_lang = "en" if lang == "en" else "zh"
    decoded_items = []
    for share_item in share_items:
        decoded = dict(share_item)
        payload = json.loads(decoded.pop("snapshot_json"))
        decoded["snapshot"] = payload.get(selected_lang) if isinstance(payload, dict) and "zh" in payload else _refresh_snapshot(payload, selected_lang)
        decoded_items.append(decoded)
    item["items"] = decoded_items
    item["item_count"] = len(decoded_items)
    item["snapshot"] = decoded_items[0]["snapshot"] if decoded_items else {}
    return item


def search_shares(
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
    conditions: List[str] = []
    params: List[Any] = []
    now = to_iso(utc_now())
    needle = query.strip().lower()
    if needle:
        like = "%{}%".format(needle)
        conditions.append("""
            (LOWER(s.code) LIKE ? OR LOWER(COALESCE(s.customer_name, '')) LIKE ?
             OR LOWER(COALESCE(s.customer_email, '')) LIKE ? OR LOWER(COALESCE(u.display_name, '')) LIKE ?
             OR LOWER(COALESCE(u.email, '')) LIKE ? OR LOWER(COALESCE(u.phone, '')) LIKE ?
             OR LOWER(COALESCE(c.product_id, '')) LIKE ? OR EXISTS (
                 SELECT 1 FROM config_share_items qi
                 JOIN saved_configs qc ON qc.id = qi.config_id
                 WHERE qi.share_id = s.id AND LOWER(COALESCE(qc.product_id, '')) LIKE ?
             ))
        """)
        params.extend([like] * 8)
    if share_status == "active":
        conditions.append("s.active = 1 AND s.expires_at > ?")
        params.append(now)
    elif share_status == "expired":
        conditions.append("s.active = 1 AND s.expires_at <= ?")
        params.append(now)
    elif share_status == "closed":
        conditions.append("s.active = 0")
    if product_id.strip():
        conditions.append("""
            (LOWER(c.product_id) = ? OR EXISTS (
                SELECT 1 FROM config_share_items pi
                JOIN saved_configs pc ON pc.id = pi.config_id
                WHERE pi.share_id = s.id AND LOWER(pc.product_id) = ?
            ))
        """)
        selected_product = product_id.strip().lower()
        params.extend([selected_product, selected_product])
    if created_from.strip():
        conditions.append("date(s.created_at) >= date(?)")
        params.append(created_from.strip())
    if created_to.strip():
        conditions.append("date(s.created_at) <= date(?)")
        params.append(created_to.strip())
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    joins = "FROM config_shares s JOIN saved_configs c ON c.id = s.config_id JOIN users u ON u.id = c.user_id"
    with get_connection() as connection:
        total = connection.execute("SELECT COUNT(*) {} {}".format(joins, where), params).fetchone()[0]
        rows = connection.execute(
            """
            SELECT s.id, s.code, s.config_id, s.created_by, s.expires_at, s.active,
                   s.view_count, s.last_viewed_at, s.created_at, s.title, s.language,
                   s.customer_name, s.customer_email, s.item_count, c.name, c.product_id,
                   u.display_name AS sender_name, u.email AS sender_email, u.phone AS sender_phone,
                   COALESCE((SELECT GROUP_CONCAT(DISTINCT sc.product_id)
                     FROM config_share_items si JOIN saved_configs sc ON sc.id = si.config_id
                     WHERE si.share_id = s.id), c.product_id) AS product_summary
            {} {}
            ORDER BY s.created_at DESC
            LIMIT ? OFFSET ?
            """.format(joins, where),
            params + [safe_page_size, (safe_page - 1) * safe_page_size],
        ).fetchall()
        metrics = connection.execute(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN active=1 AND expires_at>? THEN 1 ELSE 0 END) AS active_total, COALESCE(SUM(view_count),0) AS view_total FROM config_shares",
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
        "active_total": int(metrics["active_total"] or 0),
        "view_total": int(metrics["view_total"] or 0),
    }


def deactivate_share(share_id: str) -> bool:
    with get_connection() as connection:
        cursor = connection.execute("UPDATE config_shares SET active = 0 WHERE id = ?", (share_id,))
    return cursor.rowcount > 0


def expire_old_shares() -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            "UPDATE config_shares SET active = 0 WHERE active = 1 AND expires_at <= ?",
            (to_iso(utc_now()),),
        )
    return cursor.rowcount
