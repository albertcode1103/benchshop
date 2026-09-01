import json
import secrets
import sqlite3
import uuid
from copy import deepcopy
from datetime import timedelta
from typing import Any, Dict, List, Optional

from .database import get_connection
from .repository import get_product
from .security import to_iso, utc_now


SHARE_DAYS = 90


def build_snapshot(product_id: str, color: str, selections: Dict[str, Any], lang: str = "zh") -> Dict[str, Any]:
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
    snapshot["product"]["base_price"] = motor.get("motor_base_price_cny") if motor.get("motor_base_price_cny") is not None else snapshot["product"]["base_price"]
    snapshot["product"]["price_usd"] = motor.get("motor_base_price_usd") if motor.get("motor_base_price_usd") is not None else snapshot["product"]["price_usd"]
    snapshot["product"]["motor_option_id"] = motor.get("id")
    return snapshot


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
        query += " AND user_id = ?"
        params.append(user_id)
    with get_connection() as connection:
        row = connection.execute(query, params).fetchone()
    return _decode(row, lang)


def list_saved_configs(user_id: str, lang: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM saved_configs WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)
        ).fetchall()
    return [_decode(row, lang) for row in rows]  # type: ignore


def delete_saved_config(config_id: str, user_id: str) -> bool:
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM saved_configs WHERE id = ? AND user_id = ?", (config_id, user_id)
        )
    return cursor.rowcount > 0


def create_share(config_id: str, user_id: str) -> Dict[str, Any]:
    config = get_saved_config(config_id, user_id)
    if config is None:
        raise ValueError("Saved configuration not found")

    expires_at = to_iso(utc_now() + timedelta(days=SHARE_DAYS))
    share_id = uuid.uuid4().hex
    with get_connection() as connection:
        for _ in range(20):
            code = "{:06d}".format(secrets.randbelow(1000000))
            try:
                connection.execute(
                    """
                    INSERT INTO config_shares (id, config_id, code, created_by, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (share_id, config_id, code, user_id, expires_at),
                )
                connection.execute(
                    "UPDATE saved_configs SET status = 'shared', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (config_id,),
                )
                return {"id": share_id, "code": code, "config_id": config_id, "expires_at": expires_at}
            except sqlite3.IntegrityError:
                continue
    raise RuntimeError("Unable to allocate a share code")


def get_share(code: str, lang: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT s.id, s.code, s.config_id, s.expires_at, s.view_count, s.created_at,
                   c.name, c.product_id, c.snapshot_json,
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
        connection.execute(
            """
            UPDATE config_shares
            SET view_count = view_count + 1, last_viewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (row["id"],),
        )
    item = dict(row)
    item["snapshot"] = json.loads(item.pop("snapshot_json"))
    if lang in ("zh", "en"):
        item["snapshot"] = _refresh_snapshot(deepcopy(item["snapshot"]), lang)
    return item


def list_shares() -> List[Dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT s.id, s.code, s.config_id, s.created_by, s.expires_at, s.active,
                   s.view_count, s.last_viewed_at, s.created_at, c.name, c.product_id,
                   u.display_name AS sender_name, u.email AS sender_email, u.phone AS sender_phone
            FROM config_shares s
            JOIN saved_configs c ON c.id = s.config_id
            JOIN users u ON u.id = c.user_id
            ORDER BY s.created_at DESC
            """
        ).fetchall()
    result = [dict(row) for row in rows]
    for item in result:
        item["active"] = bool(item["active"])
    return result


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
