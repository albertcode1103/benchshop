"""Read-only PDF localization from captured bilingual source snapshots.

Never read today's catalog or copy prices/quantity/order from a source document.
Custom line names and unsupported historical translations remain as captured.
"""
from copy import deepcopy
import json
from .database import get_connection
from .inquiry_repository import inquiry_quote_items


def _source_entries(db, quote, language):
    rows = []
    if quote.get("source_inquiry_id"):
        rows = db.execute("SELECT item_type,source_id,snapshot_json FROM customer_inquiry_items WHERE inquiry_id=? ORDER BY sort_order,created_at,id", (quote["source_inquiry_id"],)).fetchall()
    elif quote.get("source_share_id"):
        rows = db.execute("SELECT item_type,source_id,snapshot_json FROM commerce_share_items WHERE share_id=? ORDER BY sort_order,created_at,id", (quote["source_share_id"],)).fetchall()
        if not rows:
            rows = db.execute("SELECT 'device_config' AS item_type,config_id AS source_id,snapshot_json FROM config_share_items WHERE share_id=? ORDER BY sort_order,created_at,id", (quote["source_share_id"],)).fetchall()
    entries = []
    for row in rows:
        try:
            stored = json.loads(row["snapshot_json"])
        except (TypeError, ValueError):
            continue
        if not isinstance(stored, dict): continue
        snapshot = stored.get(language) if "zh" in stored or "en" in stored else stored if stored.get("language", "zh") == language else None
        # Retain device positions even if a legacy translation is unavailable.
        entries.append({"item_type": row["item_type"], "source_id": row["source_id"], "snapshot": snapshot or {}})
    return entries


def _identities(items):
    sequence = 0
    for item in items:
        if item.get("kind") == "product": sequence += 1
        position = (item.get("device_sequence") or sequence) if item.get("kind") in ("product", "option", "surcharge") else 0
        yield (item.get("kind"), position, item.get("source_id")), item


def localize_quote_export(quote, language):
    result = deepcopy(quote)
    original_language = "en" if quote.get("language") == "en" else "zh"
    result["language"] = language
    if language == original_language:
        return result
    with get_connection() as db:
        original_entries = _source_entries(db, quote, original_language)
        target_entries = _source_entries(db, quote, language)
    original = dict(_identities(inquiry_quote_items({"items": original_entries}, quote.get("currency", "CNY")))) if original_entries else {}
    translated = dict(_identities(inquiry_quote_items({"items": target_entries}, quote.get("currency", "CNY")))) if target_entries else {}
    for identity, item in _identities(result.get("items") or []):
        source = original.get(identity, {})
        target = translated.get(identity, {})
        for key in ("name", "category_name", "device_specifications"):
            # Do not silently replace salesperson edits or reorder categories.
            if source.get(key) and item.get(key) == source[key] and target.get(key):
                item[key] = deepcopy(target[key])
        if not target and language == "en":
            for key in ("name", "category_name"):
                if item.get(key + "_en"): item[key] = item[key + "_en"]
    return result
