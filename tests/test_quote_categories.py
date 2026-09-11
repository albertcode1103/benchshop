from copy import deepcopy
import json
import sqlite3
from backend.inquiry_repository import inquiry_quote_items
from backend.quote_repository import _normalize_quote_items
from backend.quote_categories import recover_category_metadata, recover_quote_categories
from backend.pdf_service import _quote_groups, _quote_device_story, _styles, PdfDocumentContext, _item_table, _section_heading, _EmphasizedParagraph


def entries():
    return [{"item_type": "device_config", "snapshot": {"product": {"id": "device", "name": "Device"}, "categories": [
        {"id": "a", "name": "Same label", "sort_order": 1, "options": [{"id": "x", "name": "X", "price": 2, "sort_order": 1}]},
        {"id": "b", "name": "Same label", "sort_order": 2, "options": [{"id": "y", "name": "Y", "price": 3, "sort_order": 2}]},
    ]}}]


def test_inquiry_to_quote_preserves_distinct_categories_and_amounts():
    source = entries()
    original = deepcopy(source)
    items = _normalize_quote_items(inquiry_quote_items({"items": source}))
    assert [(i["category_id"], i["category_name"], i["category_sort_order"]) for i in items[1:]] == [("a", "Same label", 1), ("b", "Same label", 2)]
    groups, _, _, _ = _quote_groups(items)
    story, total = _quote_device_story(groups[0], 1, _styles(), PdfDocumentContext(kind="quote"))
    category_tables = [item for item in story if getattr(item, "repeatRows", None) == 2]
    assert len(category_tables) == 3  # Base price and two distinct category IDs.
    assert total == 5
    assert source == original


def test_legacy_recovery_is_metadata_only_and_does_not_merge_devices():
    items = _normalize_quote_items(inquiry_quote_items({"items": entries() + entries()}))
    for item in items:
        item.pop("category_name", None)
        item.pop("category_sort_order", None)
    original = deepcopy(items)
    recovered = recover_category_metadata(items, entries() + entries())
    assert items == original
    assert len(_quote_groups(recovered)[0]) == 2
    assert [i["price"] for i in recovered] == [i["price"] for i in items]
    assert all(i["category_name"] == "Same label" for i in recovered if i["kind"] == "option")
    assert recover_category_metadata(items, []) == items


def test_primary_pdf_headings_use_same_size_and_emphasis():
    styles = _styles()
    device = _section_heading("设备 1", styles)._cellvalues[0][0]
    table, _ = _item_table("维修工具", [{"name": "Tool", "quantity": 1}], styles, "zh", primary_group=True)
    tools = table._cellvalues[0][0]
    assert isinstance(device, _EmphasizedParagraph)
    assert isinstance(tools, _EmphasizedParagraph)
    assert device.style is tools.style
    assert device.style.fontSize == 12


def test_power_precedes_optional_categories_and_pdf_labels_use_language():
    source = entries()
    source[0]["snapshot"]["color"] = {"label": "Green"}
    source[0]["snapshot"]["categories"].append({"id": "voltage", "name": "电源", "sort_order": 9, "options": [{"id": "p", "name": "380V"}]})
    items = _normalize_quote_items(inquiry_quote_items({"items": source}, "CNY"))
    power = next(item for item in items if item.get("configuration_role") == "base_power")
    assert power["category_sort_order"] == -1
    groups, _, _, _ = _quote_groups(items)
    story, _ = _quote_device_story(groups[0], 1, _styles(), PdfDocumentContext(kind="quote", language="en"))
    summary = next(item for item in story if getattr(item, "_cellvalues", None) and len(item._cellvalues[0]) == 2)
    assert summary._cellvalues[0][0].getPlainText() == "Appearance"


def test_recovery_reads_bilingual_immutable_envelope_without_writing():
    source = entries()
    items = _normalize_quote_items(inquiry_quote_items({"items": source}))
    for item in items:
        item.pop("category_name", None)
    quote = {"items": items, "language": "en", "source_inquiry_id": "i", "lifecycle_status": "draft"}
    with sqlite3.connect(":memory:") as db:
        db.row_factory = sqlite3.Row
        db.execute("CREATE TABLE customer_inquiry_items (item_type TEXT,snapshot_json TEXT,inquiry_id TEXT,sort_order INTEGER,created_at TEXT,id TEXT)")
        db.execute("INSERT INTO customer_inquiry_items VALUES (?,?,?,0,'now','row')", ("device_config", json.dumps({"en": source[0]["snapshot"], "zh": {}}), "i"))
        changes = db.total_changes
        result = recover_quote_categories(db, quote)
        assert all(item["category_name"] == "Same label" for item in result["items"] if item["kind"] == "option")
        assert db.total_changes == changes
        quote["lifecycle_status"] = "sent"
        assert recover_quote_categories(db, quote) is quote
