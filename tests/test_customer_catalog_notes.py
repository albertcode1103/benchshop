"""Customer response boundaries; repositories are mocked, no database access."""
from copy import deepcopy
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.customer_payload import without_prices


@pytest.mark.parametrize("language", ["zh", "en"])
@pytest.mark.parametrize("catalog_type", ["tools", "accessories"])
def test_public_catalog_hides_all_note_languages(language, catalog_type):
    record = {"id": "option", "catalog_type": catalog_type, "code": "T-1",
              "name": "Public name", "description": "Public description",
              "note": "private", "note_zh": "内部", "note_en": "internal"}
    original = deepcopy(record)
    with patch("backend.config_routes.list_public_catalog_items", return_value=[record]), \
         patch("backend.catalog_cart_repository.list_public_catalog_categories", return_value=[]):
        response = TestClient(app).get(f"/api/v1/catalog/items?type={catalog_type}&lang={language}")
    assert response.status_code == 200
    assert response.json()["items"] == [{k: v for k, v in record.items() if not k.startswith("note")}]
    assert record == original  # staff/storage source retains its notes


@pytest.mark.parametrize("suffix,repository", [
    ("", "get_product"), ("/snapshot", "get_public_product_snapshot")])
def test_product_customer_endpoints_hide_legacy_and_current_notes(suffix, repository):
    option = {"id": "option", "code": "C-1", "name": "Config", "description": "Description",
              "notes": "private", "note": "private", "note_en": "private",
              "special_note": "private", "description_override_en": "private"}
    product = {"categories": [{"options": [option]}]}
    with patch(f"backend.main.{repository}", return_value=product):
        response = TestClient(app).get("/api/v1/products/fixture" + suffix)
    assert response.status_code == 200
    assert response.json()["categories"][0]["options"][0] == {
        "id": "option", "code": "C-1", "name": "Config", "description": "Description"}
    assert option["notes"] == "private"


def test_historical_share_and_cart_snapshots_preserve_customer_authored_note():
    payload = {"note": "Customer share note", "message": "Customer request", "items": [
        {"item_type": "device_config", "snapshot": {"categories": [{"options": [
            {"name": "Option", "description": "Visible", "special_note": "private", "note": "private"}
        ]}]}},
        {"item_type": "tool", "snapshot": {"name": "Tool", "note": "private", "note_en": "private"}},
        {"option_id": "accessory", "note": "private", "snapshot": {"note_zh": "private"}}
    ]}
    original = deepcopy(payload)
    result = without_prices(payload)
    assert "private" not in str(result)
    assert result["note"] == "Customer share note"
    assert result["message"] == "Customer request"
    assert result["items"][0]["snapshot"]["categories"][0]["options"][0]["description"] == "Visible"
    assert payload == original
