from contextlib import contextmanager
from copy import deepcopy
import json
import sqlite3
from backend import quote_export_language as module
from backend.inquiry_repository import inquiry_quote_items


def test_export_language_only_projects_captured_labels(monkeypatch):
    zh = {"product": {"id": "d", "name": "CR1016", "title_name": "测试设备"}, "color": {"label": "绿色"}, "categories": [{"id": "cri", "name": "测试套件", "options": [{"id": "x", "code": "X-1", "name": "卡套", "price": 5}]}]}
    en = deepcopy(zh)
    en["product"]["title_name"] = "Test Bench"
    en["color"]["label"] = "Green"
    en["categories"][0]["name"] = "Test Kits"
    en["categories"][0]["options"][0]["name"] = "Adapter"
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE customer_inquiry_items(item_type TEXT,source_id TEXT,snapshot_json TEXT,inquiry_id TEXT,sort_order INTEGER,created_at TEXT,id TEXT)")
    db.execute("INSERT INTO customer_inquiry_items VALUES('device_config','d',?,'i',0,'now','entry')", (json.dumps({"zh": zh, "en": en}),))
    @contextmanager
    def connection(): yield db
    monkeypatch.setattr(module, "get_connection", connection)
    quote = {"id": "q", "source_inquiry_id": "i", "language": "zh", "currency": "USD", "total_price": 777, "items": inquiry_quote_items({"items": [{"snapshot": zh}]}, "USD")}
    quote["items"][1]["price"] = 777
    before = deepcopy(quote)
    changes = db.total_changes
    translated = module.localize_quote_export(quote, "en")
    assert translated["items"][0]["name"] == "Test Bench"
    assert translated["items"][0]["device_specifications"][0]["value"] == "Green"
    assert translated["items"][1]["name"] == "Adapter"
    assert translated["items"][1]["category_name"] == "Test Kits"
    assert quote == before and db.total_changes == changes
    for a, b in zip(quote["items"], translated["items"]):
        for field in ("price", "quantity", "source_id", "code", "sort_order", "category_sort_order"):
            assert a.get(field) == b.get(field)
    assert translated["currency"] == "USD" and translated["total_price"] == 777
    quote["items"][1]["name"] = "业务员自定义名称"
    assert module.localize_quote_export(quote, "en")["items"][1]["name"] == "业务员自定义名称"
    db.close()


def test_direct_quote_uses_captured_english_without_modifying_original(monkeypatch):
    @contextmanager
    def connection(): yield None
    monkeypatch.setattr(module, "get_connection", connection)
    quote = {"language": "zh", "items": [{"kind": "tool", "source_id": "t", "name": "工具", "name_en": "Tool", "price": 12}]}
    assert module.localize_quote_export(quote, "en")["items"][0]["name"] == "Tool"
    assert quote["items"][0]["name"] == "工具"
