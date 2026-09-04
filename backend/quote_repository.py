"""Quotation persistence with backwards-compatible legacy reads."""

import json
import math
import uuid
from typing import Any, Dict, List, Optional

from .database import get_connection


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
            new_row = db.execute("SELECT user_id FROM commerce_quotes WHERE id = ?", (quote_id,)).fetchone()
            if new_row is not None:
                if not allow_any_owner and new_row["user_id"] != user_id:
                    raise ValueError("Quote access denied")
                db.execute(
                    """
                    UPDATE commerce_quotes
                    SET config_id = ?, source_share_id = ?, title = ?,
                        customer_name = ?, customer_email = ?, language = ?,
                        items_json = ?, total_price = ?, currency = ?,
                        updated_at = CURRENT_TIMESTAMP
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
    results = [_decode(row, 2) for row in new_rows] + [_decode(row, 1) for row in legacy_rows]
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


def delete_quote(quote_id: str, user_id: Optional[str] = None) -> bool:
    owner_clause = "AND user_id = ?" if user_id else ""
    params = (quote_id, user_id) if user_id else (quote_id,)
    with get_connection() as db:
        cursor = db.execute("DELETE FROM commerce_quotes WHERE id = ? {}".format(owner_clause), params)
        if cursor.rowcount:
            return True
        cursor = db.execute("DELETE FROM quotes WHERE id = ? {}".format(owner_clause), params)
    return cursor.rowcount > 0


def list_reference_prices() -> Dict[str, List[Dict[str, Any]]]:
    with get_connection() as db:
        products = db.execute("SELECT id, name, base_price, price_usd FROM products WHERE enabled = 1").fetchall()
        options = db.execute("SELECT id, code, name, price, price_usd FROM options WHERE enabled = 1").fetchall()
    return {"products": [dict(row) for row in products], "options": [dict(row) for row in options]}
