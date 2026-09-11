"""Recover display metadata from immutable business snapshots, never live catalog."""
import json


def recover_category_metadata(items, entries, language="zh"):
    metadata = {}
    sequence = 0
    for entry in entries:
        if entry.get("item_type", "device_config") != "device_config":
            continue
        sequence += 1
        snapshot = entry.get("snapshot") or {}
        product_id = (snapshot.get("product") or {}).get("id")
        for category_index, category in enumerate(snapshot.get("categories") or []):
            for option_index, option in enumerate(category.get("options") or []):
                label = category.get("name") or ""
                if language == "en" and snapshot.get("language", "zh") != "en":
                    label = category.get("name_en") or ""
                metadata[(sequence, product_id, option.get("id"))] = {
                    "category_id": category.get("id") or "",
                    "category_name": label,
                    "category_sort_order": -1 if category.get("id") in ("power", "voltage") else category.get("sort_order", category_index),
                    "sort_order": option.get("sort_order", option_index),
                }
    products = {item.get("device_sequence"): item.get("source_id") for item in items if item.get("kind") == "product"}
    result = []
    for item in items:
        item = dict(item)
        if item.get("kind") in ("option", "surcharge"):
            candidate = metadata.get((item.get("device_sequence"), products.get(item.get("device_sequence")), item.get("source_id")))
            if candidate and (not item.get("category_id") or item["category_id"] == candidate["category_id"]):
                for key, value in candidate.items():
                    if item.get(key) in (None, ""):
                        item[key] = value
        result.append(item)
    return result


def recover_quote_categories(db, quote):
    if not quote or quote.get("lifecycle_status") == "sent":
        return quote
    rows = []
    if quote.get("source_inquiry_id"):
        rows = db.execute("SELECT item_type,snapshot_json FROM customer_inquiry_items WHERE inquiry_id=? ORDER BY sort_order,created_at,id", (quote["source_inquiry_id"],)).fetchall()
    elif quote.get("source_share_id"):
        for table in ("commerce_share_items", "config_share_items"):
            rows = db.execute(f"SELECT item_type,snapshot_json FROM {table} WHERE share_id=? ORDER BY sort_order,created_at,id", (quote["source_share_id"],)).fetchall()
            if rows:
                break
    # A saved configuration is editable; it is not a safe fallback for history.
    entries = []
    language = "en" if quote.get("language") == "en" else "zh"
    for row in rows:
        try:
            snapshot = json.loads(row["snapshot_json"])
            if isinstance(snapshot, dict):
                # Commerce/inquiry rows store bilingual envelopes; legacy
                # config-share rows store a direct device snapshot.
                if "zh" in snapshot or "en" in snapshot:
                    snapshot = snapshot.get(language)
                    if not isinstance(snapshot, dict):
                        continue
                    snapshot = dict(snapshot, language=language)
                entries.append({"item_type": row["item_type"], "snapshot": snapshot})
        except (TypeError, ValueError):
            continue
    if entries:
        quote = dict(quote, items=recover_category_metadata(quote.get("items") or [], entries, quote.get("language") or "zh"))
    return quote
