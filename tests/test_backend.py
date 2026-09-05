import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path


TEST_DIRECTORY = tempfile.TemporaryDirectory(prefix="boten-tests-")
TEST_DATABASE = Path(TEST_DIRECTORY.name) / "boten-test.db"
TEST_UPLOADS = Path(TEST_DIRECTORY.name) / "uploads"
os.environ["BOTEN_DATABASE_PATH"] = str(TEST_DATABASE)
os.environ["BOTEN_UPLOAD_DIR"] = str(TEST_UPLOADS)

from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from backend.admin_catalog_repository import (
    config_category_references,
    config_option_references,
    create_config_category,
    create_config_option,
    delete_config_category,
    delete_config_option,
    get_admin_product,
    list_config_categories,
    replace_option_mappings,
    update_product_option_override,
)
from backend.audit_catalog import audit_catalog
from backend.config_repository import build_snapshot, create_share, get_share, list_saved_configs, save_config
from backend.commerce_repository import _normalize_refs, search_all_shares
from backend.catalog_refactor_repository import CatalogValidationError, create_catalog_item, get_product_editor, save_product_editor
from backend.customer_payload import PRICE_KEYS, without_prices
from backend.pricing_service import calculate_product_price
from backend.translation_service import translation_draft
from backend.config_routes import staff_user
from backend.database import get_connection
from backend.database_maintenance import create_backup, restore_backup, verify_database
from backend.media_routes import image_extension, store_image
from backend.main import app
from backend.pdf_service import configuration_pdf, quote_pdf
from backend.repository import get_product, get_public_product_snapshot, list_products
from backend.seed import seed
from backend.user_repository import authenticate, create_session, create_user, get_user_by_token


def sample_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (2, 3), (20, 125, 63)).save(output, format="PNG")
    return output.getvalue()


class BackendWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        seed()

    @classmethod
    def tearDownClass(cls) -> None:
        TEST_DIRECTORY.cleanup()

    def test_catalog_and_schema(self) -> None:
        products = list_products("zh")
        self.assertEqual(7, len(products))
        english = list_products("en")
        self.assertEqual({item["id"] for item in products}, {item["id"] for item in english})
        with get_connection() as database:
            columns = {row[1] for row in database.execute("PRAGMA table_info(product_options)")}
        self.assertIn("description_override_en", columns)
        cr318pro = get_product("cr318pro")
        self.assertIsNone(cr318pro["colors"][0]["image_path"])

    def test_cart_batch_limit_counts_devices_separately_from_catalog_items(self) -> None:
        catalog_refs = [{"item_type": "tool", "id": "tool-{}".format(index)} for index in range(21)]
        self.assertEqual(21, len(_normalize_refs(catalog_refs)))

        with self.assertRaises(CatalogValidationError) as device_limit:
            _normalize_refs([{"item_type": "device_config", "id": "device-{}".format(index)} for index in range(101)])
        self.assertEqual("BATCH_SELECTION_LIMIT", device_limit.exception.code)

        with self.assertRaises(CatalogValidationError) as cart_limit:
            _normalize_refs([{"item_type": "accessory", "id": "accessory-{}".format(index)} for index in range(101)])
        self.assertEqual("CART_BATCH_SELECTION_LIMIT", cart_limit.exception.code)

    def test_customer_payload_removes_nested_prices_without_mutating_source(self) -> None:
        source = {
            "id": "sample",
            "price": 12,
            "nested": [{"name": "Visible", "price_usd_minor": 500, "pricing": {"USD": 5}}],
            "tuple": ({"grand_total": "9.00", "description": "Keep"},),
        }
        result = without_prices(source)

        def assert_safe(value):
            if isinstance(value, dict):
                self.assertTrue(PRICE_KEYS.isdisjoint(value.keys()))
                for child in value.values():
                    assert_safe(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    assert_safe(child)

        assert_safe(result)
        self.assertEqual("Visible", result["nested"][0]["name"])
        self.assertEqual("Keep", result["tuple"][0]["description"])
        self.assertEqual(12, source["price"])

    def test_legacy_catalog_hides_and_protects_v2_root_categories(self) -> None:
        root_ids = ("catalog-optional", "catalog-tools", "catalog-accessories")
        inserted = []
        with get_connection() as database:
            for sort_order, category_id in enumerate(root_ids):
                exists = database.execute(
                    "SELECT 1 FROM categories WHERE id = ?", (category_id,)
                ).fetchone()
                if exists is None:
                    database.execute(
                        """
                        INSERT INTO categories
                            (id, name, name_en, description, description_en,
                             multiple, sort_order, parent_id, catalog_type,
                             enabled, version, translation_status)
                        VALUES (?, ?, ?, '', '', 1, ?, NULL, ?, 1, 1, 'reviewed')
                        """,
                        (category_id, category_id, category_id, sort_order, category_id.split("-", 1)[1]),
                    )
                    inserted.append(category_id)
        try:
            visible_ids = {item["id"] for item in list_config_categories()}
            self.assertTrue(visible_ids.isdisjoint(root_ids))
            for category_id in root_ids:
                self.assertTrue(config_category_references(category_id)["protected"])
                self.assertFalse(delete_config_category(category_id))
        finally:
            if inserted:
                with get_connection() as database:
                    database.executemany(
                        "DELETE FROM categories WHERE id = ?",
                        [(category_id,) for category_id in inserted],
                    )

    def test_refactored_product_editor_and_pricing_service(self) -> None:
        product_id = "pricing-test-product"
        with get_connection() as database:
            database.execute(
                """
                INSERT INTO products
                    (id, name, name_en, title_name, title_name_en,
                     description, description_en, base_price, price_usd,
                     enabled, sort_order, version, translation_status)
                VALUES (?, 'TEST', 'TEST', '测试设备', 'Test Product', '', '',
                        0, 0, 1, 999, 1, 'reviewed')
                """,
                (product_id,),
            )
            database.execute(
                """
                INSERT INTO product_colors
                    (product_id, code, label, label_en, is_default, enabled)
                VALUES (?, 'green', '绿色', 'Green', 1, 1)
                """,
                (product_id,),
            )
        try:
            saved = save_product_editor(
                product_id,
                version=1,
                model="BOTEN TEST",
                product_name_zh="测试设备",
                product_name_en="Test Product",
                overview_zh="测试概况",
                overview_en="Test overview",
                enabled=True,
                colors=[
                    {
                        "id": "green",
                        "name_zh": "绿色",
                        "name_en": "Green",
                        "display_color": "#147d3f",
                        "is_default": True,
                        "enabled": True,
                        "translation_status": "reviewed",
                    }
                ],
                specifications=[
                    {
                        "id": "pricing-test-spec",
                        "label": "最大转速",
                        "label_en": "Maximum speed",
                        "value": "3000 rpm",
                        "value_en": "3000 rpm",
                    }
                ],
                groups=[
                    {
                        "id": "base-pricing-test-motor",
                        "option_type": "motor",
                        "options": [
                            {
                                "id": "base-pricing-test-motor-1",
                                "name_zh": "测试电机",
                                "name_en": "Test Motor",
                                "enabled": True,
                            }
                        ],
                    },
                    {
                        "id": "base-pricing-test-power",
                        "option_type": "power",
                        "options": [
                            {
                                "id": "base-pricing-test-power-free",
                                "name_zh": "免费电源",
                                "name_en": "Included Power",
                                "price_cny_minor": 0,
                                "price_usd_minor": 0,
                                "price_confirmed": True,
                                "is_free": True,
                                "enabled": True,
                            }
                        ],
                    },
                ],
                variants=[
                    {
                        "id": "price-pricing-test",
                        "motor_option_id": "base-pricing-test-motor-1",
                        "channel_option_id": None,
                        "price_cny_minor": 123400,
                        "price_usd_minor": 55000,
                        "price_confirmed": True,
                        "enabled": True,
                    }
                ],
                optional_config_ids=["cri-1016"],
                optional_config_overrides={
                    "cri-1016": {
                        "description_override": "当前设备专有标注",
                        "description_override_en": "Device-specific note",
                    }
                },
            )
            self.assertEqual(2, saved["version"])
            self.assertEqual(["cri-1016"], saved["optional_config_ids"])
            self.assertEqual(2, len(saved["base_option_groups"]))
            self.assertEqual("#147d3f", saved["colors"][0]["display_color"])
            self.assertEqual("最大转速", saved["specifications"][0]["label"])
            public_snapshot = get_public_product_snapshot(product_id, "en")
            self.assertEqual(2, public_snapshot["schema_version"])
            self.assertEqual("BOTEN TEST", public_snapshot["model"])
            self.assertEqual("Green", public_snapshot["colors"][0]["name"])
            self.assertEqual(["motor", "power"], [group["type"] for group in public_snapshot["base_option_groups"]])
            self.assertEqual("Maximum speed", public_snapshot["specifications"][0]["label"])
            self.assertEqual(
                "Device-specific note",
                public_snapshot["optional_categories"][0]["options"][0]["special_note"],
            )
            chinese_snapshot = get_public_product_snapshot(product_id, "zh")
            self.assertEqual(
                "当前设备专有标注",
                chinese_snapshot["optional_categories"][0]["options"][0]["special_note"],
            )
            note_category = next(
                category for category in chinese_snapshot["optional_categories"]
                if any(option["id"] == "cri-1016" for option in category["options"])
            )
            saved_snapshot = build_snapshot(
                product_id,
                "green",
                {
                    "motor": "base-pricing-test-motor-1",
                    "voltage": "base-pricing-test-power-free",
                    note_category["id"]: ["cri-1016"],
                },
                "zh",
            )
            saved_note = next(
                option["special_note"]
                for category in saved_snapshot["categories"]
                for option in category["options"]
                if option["id"] == "cri-1016"
            )
            self.assertEqual("当前设备专有标注", saved_note)
            price = calculate_product_price(
                product_id,
                motor_option_id="base-pricing-test-motor-1",
                channel_option_id=None,
                power_option_id="base-pricing-test-power-free",
                optional_config_ids=[],
                currency="CNY",
                language="zh",
            )
            self.assertEqual("1234.00", price["base_price"])
            self.assertEqual("1234.00", price["grand_total"])
            self.assertTrue(price["price_confirmed"])
            with TestClient(app) as client:
                response = client.get("/api/v1/products/{}/snapshot?lang=en".format(product_id))
                self.assertEqual(200, response.status_code, response.text)
                public_preview = client.post(
                    "/api/v1/pricing/preview",
                    json={
                        "product_id": product_id,
                        "motor_option_id": "base-pricing-test-motor-1",
                        "channel_option_id": None,
                        "power_option_id": "base-pricing-test-power-free",
                        "optional_config_ids": [],
                        "currency": "USD",
                        "lang": "en",
                    },
                )
                self.assertEqual(401, public_preview.status_code, public_preview.text)
                staff = create_user(
                    "pricing-staff@example.com", None, "password123",
                    role="sales", display_name="Pricing Staff",
                )
                preview = client.post(
                    "/api/v1/pricing/preview",
                    headers={"Authorization": "Bearer {}".format(create_session(staff)["token"])},
                    json={
                        "product_id": product_id,
                        "motor_option_id": "base-pricing-test-motor-1",
                        "channel_option_id": None,
                        "power_option_id": "base-pricing-test-power-free",
                        "optional_config_ids": [],
                        "currency": "USD",
                        "lang": "en",
                    },
                )
                self.assertEqual(200, preview.status_code, preview.text)
                self.assertEqual("550.00", preview.json()["grand_total"])
            with self.assertRaises(CatalogValidationError) as conflict:
                save_product_editor(
                    product_id,
                    version=1,
                    model="BOTEN TEST",
                    product_name_zh="测试设备",
                    product_name_en="Test Product",
                    overview_zh="",
                    overview_en="",
                    enabled=True,
                    groups=[],
                    variants=[],
                    optional_config_ids=[],
                )
            self.assertEqual("BASE_OPTION_GROUP_REQUIRED", conflict.exception.code)
        finally:
            with get_connection() as database:
                database.execute("DELETE FROM products WHERE id = ?", (product_id,))

    def test_channel_only_base_price_ignores_selected_motor(self) -> None:
        product_id = "channel-pricing-test-product"
        motor_id = "base-channel-pricing-motor"
        channel_2_id = "base-channel-pricing-channel-2"
        channel_4_id = "base-channel-pricing-channel-4"
        with get_connection() as database:
            database.execute(
                """
                INSERT INTO products
                    (id, name, name_en, title_name, title_name_en,
                     description, description_en, base_price, price_usd,
                     enabled, sort_order, version, translation_status)
                VALUES (?, 'CHANNEL TEST', 'CHANNEL TEST', '通道定价测试',
                        'Channel pricing test', '', '', 0, 0, 1, 999, 1, 'reviewed')
                """,
                (product_id,),
            )
            database.execute(
                """
                INSERT INTO product_colors
                    (product_id, code, label, label_en, is_default, enabled)
                VALUES (?, 'default', '默认', 'Default', 1, 1)
                """,
                (product_id,),
            )
        try:
            save_product_editor(
                product_id,
                version=1,
                model="CHANNEL TEST",
                product_name_zh="通道定价测试",
                product_name_en="Channel pricing test",
                overview_zh="",
                overview_en="",
                enabled=True,
                colors=[{
                    "id": "default", "name_zh": "默认", "name_en": "Default",
                    "is_default": True, "enabled": True,
                }],
                specifications=[],
                groups=[
                    {
                        "id": "base-channel-pricing-motor-group",
                        "option_type": "motor",
                        "options": [{
                            "id": motor_id, "name_zh": "测试电机",
                            "name_en": "Test motor", "enabled": True,
                        }],
                    },
                    {
                        "id": "base-channel-pricing-channel-group",
                        "option_type": "channel",
                        "enabled": True,
                        "options": [
                            {"id": channel_2_id, "name_zh": "2 通道", "name_en": "2 Channels", "enabled": True},
                            {"id": channel_4_id, "name_zh": "4 通道", "name_en": "4 Channels", "enabled": True},
                        ],
                    },
                    {
                        "id": "base-channel-pricing-power-group",
                        "option_type": "power",
                        "options": [{
                            "id": "base-channel-pricing-power", "name_zh": "标准电源",
                            "name_en": "Standard power", "is_free": True,
                            "price_confirmed": True, "enabled": True,
                        }],
                    },
                ],
                variants=[
                    {
                        "id": "price-channel-only-2", "motor_option_id": None,
                        "channel_option_id": channel_2_id,
                        "price_cny_minor": 6280000, "price_usd_minor": 980000,
                        "price_confirmed": True, "enabled": True,
                    },
                    {
                        "id": "price-channel-only-4", "motor_option_id": None,
                        "channel_option_id": channel_4_id,
                        "price_cny_minor": 8280000, "price_usd_minor": 1280000,
                        "price_confirmed": True, "enabled": True,
                    },
                ],
                optional_config_ids=[],
            )
            cny = calculate_product_price(
                product_id,
                motor_option_id=motor_id,
                channel_option_id=channel_2_id,
                power_option_id=None,
                optional_config_ids=[],
                currency="CNY",
            )
            usd = calculate_product_price(
                product_id,
                motor_option_id=motor_id,
                channel_option_id=channel_4_id,
                power_option_id=None,
                optional_config_ids=[],
                currency="USD",
            )
            self.assertEqual("62800.00", cny["base_price"])
            self.assertEqual("12800.00", usd["base_price"])
        finally:
            with get_connection() as database:
                database.execute("DELETE FROM products WHERE id = ?", (product_id,))

    def test_authentication_and_session(self) -> None:
        user = create_user("workflow@example.com", None, "password123", display_name="Workflow")
        authenticated = authenticate("WORKFLOW@example.com", "password123")
        self.assertEqual(user["id"], authenticated["id"])
        session = create_session(authenticated)
        with get_connection() as database:
            fresh_last_seen = database.execute("SELECT last_seen_at FROM sessions WHERE user_id = ?", (user["id"],)).fetchone()[0]
        self.assertEqual(user["id"], get_user_by_token(session["token"])["id"])
        with get_connection() as database:
            unchanged_last_seen = database.execute("SELECT last_seen_at FROM sessions WHERE user_id = ?", (user["id"],)).fetchone()[0]
            stale_last_seen = "2000-01-01 00:00:00"
            database.execute("UPDATE sessions SET last_seen_at = ? WHERE user_id = ?", (stale_last_seen, user["id"]))
        self.assertEqual(fresh_last_seen, unchanged_last_seen)
        self.assertEqual(user["id"], get_user_by_token(session["token"])["id"])
        with get_connection() as database:
            refreshed_last_seen = database.execute("SELECT last_seen_at FROM sessions WHERE user_id = ?", (user["id"],)).fetchone()[0]
        self.assertNotEqual(refreshed_last_seen, stale_last_seen)
        self.assertIsNone(authenticate("workflow@example.com", "wrong-password"))

    def test_phone_registration_and_login_use_international_format(self) -> None:
        with TestClient(app) as client:
            registered = client.post("/api/v1/auth/register", json={"display_name": "Phone User", "email": "phone-user@example.com", "phone_country": "CN", "phone": "1590000000", "password": "password123"})
            self.assertEqual(201, registered.status_code, registered.text)
            self.assertEqual("1590000000", registered.json()["user"]["phone"])
            self.assertEqual("CN", registered.json()["user"]["phone_country"])
            logged_in = client.post("/api/v1/auth/login", json={"phone_country": "CN", "phone": "1590000000", "password": "password123"})
            self.assertEqual(200, logged_in.status_code, logged_in.text)
            invalid = client.post("/api/v1/auth/register", json={"display_name": "Invalid Phone", "email": "invalid-phone@example.com", "phone_country": "CN", "phone": "1590000000x", "password": "password123"})
            self.assertEqual(422, invalid.status_code, invalid.text)
            incomplete = client.post("/api/v1/auth/register", json={"email": "missing-name@example.com", "phone_country": "CN", "phone": "1590000001", "password": "password123"})
            self.assertEqual(422, incomplete.status_code, incomplete.text)
            chinese_phone_only = client.post(
                "/api/v1/auth/register",
                headers={"X-UI-Language": "zh-CN"},
                json={"display_name": "Chinese Phone User", "phone_country": "CN", "phone": "1590000002", "password": "password123"},
            )
            self.assertEqual(201, chinese_phone_only.status_code, chinese_phone_only.text)
            self.assertIsNone(chinese_phone_only.json()["user"]["email"])
            english_missing_email = client.post(
                "/api/v1/auth/register",
                headers={"X-UI-Language": "en"},
                json={"display_name": "English User", "phone_country": "CN", "phone": "1590000003", "password": "password123"},
            )
            self.assertEqual(422, english_missing_email.status_code, english_missing_email.text)
            self.assertEqual("ACCOUNT_EMAIL_REQUIRED", english_missing_email.json()["error"]["code"])
            profile_headers = {"Authorization": "Bearer {}".format(chinese_phone_only.json()["session"]["token"])}
            profile = client.patch(
                "/api/v1/auth/profile/details",
                headers=profile_headers,
                json={"display_name": "中文客户", "gender": "other", "birth_date": "1990-05-06", "signature": "柴油测试设备", "version": chinese_phone_only.json()["user"]["version"]},
            )
            self.assertEqual(200, profile.status_code, profile.text)
            self.assertEqual("other", profile.json()["gender"])
            self.assertEqual("1990-05-06", profile.json()["birth_date"])
            self.assertEqual("柴油测试设备", profile.json()["signature"])

    def test_save_and_share_configuration(self) -> None:
        user = create_user("share@example.com", None, "password123", display_name="Share User")
        product = get_product("cr1016")
        self.assertIsNotNone(product)
        selections = {}
        for category in product["categories"]:
            if not category["multiple"] and category["options"]:
                selections[category["id"]] = category["options"][0]["id"]
        snapshot = build_snapshot(product["id"], product["colors"][0]["code"], selections)
        saved = save_config(user["id"], "Test configuration", product["id"], snapshot)
        share = create_share(saved["id"], user["id"])
        self.assertRegex(share["code"], r"^\d{6}$")
        shared = get_share(share["code"])
        self.assertEqual(saved["id"], shared["config_id"])
        self.assertEqual("Share User", shared["sender_name"])

    def test_cart_overwrite_bundle_share_pdf_and_archive_workflow(self) -> None:
        user = create_user("bundle@example.com", None, "password123", display_name="Bundle Customer")
        token = create_session(user)["token"]
        headers = {"Authorization": "Bearer {}".format(token)}
        product = get_product("cr1016")
        color = product["colors"][0]["code"]
        selections = {
            category["id"]: category["options"][0]["id"]
            for category in product["categories"]
            if not category["multiple"] and category["options"]
        }
        payload = {"name": "Bundle A", "product_id": product["id"], "color": color, "selections": selections, "lang": "zh"}

        with TestClient(app) as client:
            first = client.post("/api/v1/configs", headers=headers, json=payload)
            second = client.post("/api/v1/configs", headers=headers, json={**payload, "name": "Bundle B"})
            self.assertEqual(201, first.status_code, first.text)
            self.assertEqual(201, second.status_code, second.text)

            first_config = first.json()
            updated = client.put(
                "/api/v1/configs/{}".format(first_config["id"]),
                headers=headers,
                json={**payload, "name": "Bundle A updated", "version": first_config["version"]},
            )
            self.assertEqual(200, updated.status_code, updated.text)
            self.assertEqual(first_config["id"], updated.json()["id"])
            self.assertEqual(first_config["version"] + 1, updated.json()["version"])
            conflict = client.put(
                "/api/v1/configs/{}".format(first_config["id"]),
                headers=headers,
                json={**payload, "version": first_config["version"]},
            )
            self.assertEqual(409, conflict.status_code, conflict.text)
            self.assertEqual("SAVED_CONFIG_VERSION_CONFLICT", conflict.json()["error"]["code"])

            config_ids = [first_config["id"], second.json()["id"]]
            share = client.post("/api/v1/config-shares", headers=headers, json={"config_ids": config_ids, "lang": "zh"})
            self.assertEqual(201, share.status_code, share.text)
            self.assertEqual(2, share.json()["item_count"])
            code = share.json()["code"]

            staff = create_user("bundle-sales@example.com", None, "password123", role="sales", display_name="Bundle Sales")
            staff_headers = {"Authorization": "Bearer {}".format(create_session(staff)["token"])}
            preview = client.get("/api/v1/staff/shares/{}/preview?lang=en".format(code), headers=staff_headers)
            self.assertEqual(200, preview.status_code, preview.text)
            self.assertEqual(2, len(preview.json()["items"]))
            self.assertEqual(0, preview.json()["view_count"])
            frozen_color = preview.json()["items"][0]["snapshot"]["color"]["code"]
            alternate_color = next((item["code"] for item in product["colors"] if item["code"] != color), color)
            changed_after_share = client.put(
                "/api/v1/configs/{}".format(first_config["id"]), headers=headers,
                json={**payload, "color": alternate_color, "version": updated.json()["version"]},
            )
            self.assertEqual(200, changed_after_share.status_code, changed_after_share.text)
            frozen_preview = client.get("/api/v1/staff/shares/{}/preview?lang=en".format(code), headers=staff_headers)
            self.assertEqual(frozen_color, frozen_preview.json()["items"][0]["snapshot"]["color"]["code"])
            filtered = client.get("/api/v1/staff/shares?query={}&status=active&page=1&page_size=5".format(code), headers=staff_headers)
            self.assertEqual(200, filtered.status_code, filtered.text)
            self.assertEqual(1, filtered.json()["total"])
            self.assertEqual(2, filtered.json()["items"][0]["item_count"])
            self.assertEqual(2, filtered.json()["items"][0]["device_count"])
            self.assertEqual(0, filtered.json()["items"][0]["tool_quantity"])
            self.assertEqual(0, filtered.json()["items"][0]["accessory_quantity"])

            admin = create_user("bundle-admin@example.com", None, "password123", role="admin", display_name="Bundle Admin")
            admin_headers = {"Authorization": "Bearer {}".format(create_session(admin)["token"])}
            closed = client.patch("/api/v1/admin/shares/{}/status".format(share.json()["id"]), headers=admin_headers, json={"active": False})
            self.assertEqual(200, closed.status_code, closed.text)
            closed_again = client.patch("/api/v1/admin/shares/{}/status".format(share.json()["id"]), headers=admin_headers, json={"active": False})
            self.assertEqual(200, closed_again.status_code, closed_again.text)
            reopened = client.patch("/api/v1/admin/shares/{}/status".format(share.json()["id"]), headers=admin_headers, json={"active": True})
            self.assertEqual(200, reopened.status_code, reopened.text)

            pdf = client.post("/api/v1/config-exports/pdf", headers=headers, json={"config_ids": config_ids, "lang": "en"})
            self.assertEqual(200, pdf.status_code, pdf.text)
            self.assertEqual("application/pdf", pdf.headers["content-type"])
            self.assertTrue(pdf.content.startswith(b"%PDF"))

            archived = client.post("/api/v1/configs/batch-archive", headers=headers, json={"config_ids": config_ids, "lang": "zh"})
            self.assertEqual(200, archived.status_code, archived.text)
            self.assertEqual(2, archived.json()["archived_count"])
            self.assertEqual([], client.get("/api/v1/configs", headers=headers).json()["items"])
            preserved_share = client.get("/api/v1/staff/shares/{}/preview".format(code), headers=staff_headers)
            self.assertEqual(200, preserved_share.status_code, preserved_share.text)
            self.assertEqual(2, len(preserved_share.json()["items"]))

    def test_saved_config_refreshes_current_bilingual_color_names(self) -> None:
        user = create_user("color-refresh@example.com", None, "password123", display_name="Color Refresh")
        product = get_product("cr1016")
        color_code = product["colors"][0]["code"]
        saved = save_config(user["id"], "Color refresh", product["id"], build_snapshot(product["id"], color_code, {}))
        with get_connection() as database:
            original = database.execute("SELECT label, label_en FROM product_colors WHERE product_id=? AND code=?", (product["id"], color_code)).fetchone()
            database.execute("UPDATE product_colors SET label=?, label_en=? WHERE product_id=? AND code=?", ("深绿色", "Deep Green", product["id"], color_code))
        try:
            chinese = next(item for item in list_saved_configs(user["id"], "zh") if item["id"] == saved["id"])
            english = next(item for item in list_saved_configs(user["id"], "en") if item["id"] == saved["id"])
            self.assertEqual("深绿色", chinese["snapshot"]["color"]["label"])
            self.assertEqual("Deep Green", english["snapshot"]["color"]["label"])
        finally:
            with get_connection() as database:
                database.execute("UPDATE product_colors SET label=?, label_en=? WHERE product_id=? AND code=?", (original["label"], original["label_en"], product["id"], color_code))

    def test_bilingual_product_option_override(self) -> None:
        product = get_product("cr1016")
        option = next(item for category in product["categories"] for item in category["options"])
        updated = update_product_option_override("cr1016", option["id"], "中文专属说明", "English product-specific note")
        self.assertIsNotNone(updated)
        english = get_product("cr1016", "en")
        translated = next(item for category in english["categories"] for item in category["options"] if item["id"] == option["id"])
        self.assertEqual("English product-specific note", translated["special_note"])
        self.assertNotEqual("English product-specific note", translated["description"])

    def test_disabled_product_option_retains_bilingual_note(self) -> None:
        product_id = "cr1016"
        product = get_admin_product(product_id)
        selected_ids = [option["id"] for category in product["categories"] for option in category["options"] if option["selected"]]
        target = next(option for category in product["categories"] if category["id"] not in ("motor", "voltage") for option in category["options"] if option["selected"])
        original_zh = target.get("description_override")
        original_en = target.get("description_override_en")
        try:
            update_product_option_override(product_id, target["id"], "保留的中文标注", "Retained English note")
            replace_option_mappings(product_id, [option_id for option_id in selected_ids if option_id != target["id"]])
            disabled = get_admin_product(product_id)
            disabled_option = next(option for category in disabled["categories"] for option in category["options"] if option["id"] == target["id"])
            self.assertFalse(disabled_option["selected"])
            self.assertEqual("保留的中文标注", disabled_option["description_override"])
            self.assertNotIn(target["id"], [option["id"] for category in get_product(product_id)["categories"] for option in category["options"]])

            replace_option_mappings(product_id, selected_ids)
            restored = next(option for category in get_product(product_id, "en")["categories"] for option in category["options"] if option["id"] == target["id"])
            self.assertEqual("Retained English note", restored["special_note"])
        finally:
            replace_option_mappings(product_id, selected_ids)
            update_product_option_override(product_id, target["id"], original_zh, original_en)

    def test_staff_role_boundary(self) -> None:
        self.assertEqual("sales", staff_user({"role": "sales"})["role"])
        with self.assertRaises(HTTPException) as failure:
            staff_user({"role": "customer"})
        self.assertEqual(403, failure.exception.status_code)

    def test_backup_and_restore(self) -> None:
        backup_dir = Path(TEST_DIRECTORY.name) / "backups"
        backup = create_backup(backup_dir, keep=3)
        verify_database(backup)
        with get_connection() as database:
            original = database.execute("SELECT name FROM products WHERE id='cr1016'").fetchone()[0]
            database.execute("UPDATE products SET name='Temporary value' WHERE id='cr1016'")
        restore_backup(backup, "RESTORE", backup_dir)
        connection = sqlite3.connect(str(TEST_DATABASE))
        try:
            restored = connection.execute("SELECT name FROM products WHERE id='cr1016'").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(original, restored)

    def test_catalog_audit_runs(self) -> None:
        report = audit_catalog()
        self.assertEqual(7, report["summary"]["products"])
        self.assertEqual(75, report["summary"]["options"])

    def test_catalog_image_storage(self) -> None:
        upload_dir = Path(TEST_DIRECTORY.name) / "uploads"
        content = sample_png()
        self.assertEqual("png", image_extension(content))
        media_path = store_image(content, upload_dir)
        self.assertRegex(media_path, r"^/api/v1/media/[a-f0-9]{32}\.png$")
        self.assertTrue((upload_dir / Path(media_path).name).is_file())
        with self.assertRaises(ValueError):
            store_image(b"not-an-image", upload_dir)

    def test_admin_media_and_delete_api(self) -> None:
        admin = create_user("api-admin@example.com", None, "password123", role="admin", display_name="API Admin")
        token = create_session(admin)["token"]
        headers = {"Authorization": "Bearer {}".format(token), "Content-Type": "image/png"}
        with TestClient(app) as client:
            uploaded = client.post(
                "/api/v1/admin/media?filename=test.png",
                headers=headers,
                content=sample_png(),
            )
            self.assertEqual(201, uploaded.status_code, uploaded.text)
            media_path = uploaded.json()["path"]
            self.assertEqual(2, uploaded.json()["width"])
            self.assertEqual(3, uploaded.json()["height"])
            self.assertEqual(200, client.get(media_path).status_code)
            protected = client.delete("/api/v1/admin/config-catalog/options/cri-1016", headers={"Authorization": "Bearer {}".format(token)})
            self.assertEqual(409, protected.status_code)
            created_category = client.post(
                "/api/v1/admin/config-catalog/categories",
                headers={"Authorization": "Bearer {}".format(token)},
                json={"name": "审计测试分类", "name_en": "Audit test category"},
            )
            self.assertEqual(201, created_category.status_code, created_category.text)
            audit_response = client.get("/api/v1/admin/audit-logs", headers={"Authorization": "Bearer {}".format(token)})
            self.assertEqual(200, audit_response.status_code, audit_response.text)
            self.assertTrue(any(item["details"].get("path") == "/api/v1/admin/config-catalog/categories" for item in audit_response.json()["items"]))

    def test_admin_catalog_crud_api_round_trip(self) -> None:
        admin = create_user("crud-admin@example.com", None, "password123", role="admin", display_name="CRUD Admin")
        headers = {"Authorization": "Bearer {}".format(create_session(admin)["token"])}
        with TestClient(app) as client:
            category_response = client.post("/api/v1/admin/config-catalog/categories", headers=headers, json={
                "name": "临时回归分类", "name_en": "Temporary regression category", "multiple": True,
            })
            self.assertEqual(201, category_response.status_code, category_response.text)
            category = category_response.json()
            option_response = client.post("/api/v1/admin/config-catalog/options", headers=headers, json={
                "category_id": category["id"], "code": "REG-001", "name": "临时配置", "name_en": "Temporary option", "price": 100, "price_usd": 15,
            })
            self.assertEqual(201, option_response.status_code, option_response.text)
            option = option_response.json()
            edited = client.patch("/api/v1/admin/config-catalog/options/{}".format(option["id"]), headers=headers, json={"name": "临时配置已修改", "price": 120})
            self.assertEqual(200, edited.status_code, edited.text)
            self.assertEqual("临时配置已修改", edited.json()["name"])
            self.assertEqual(204, client.delete("/api/v1/admin/config-catalog/options/{}".format(option["id"]), headers=headers).status_code)
            self.assertEqual(204, client.delete("/api/v1/admin/config-catalog/categories/{}".format(category["id"]), headers=headers).status_code)

            product = client.get("/api/v1/admin/products/cr1016", headers=headers).json()
            empty_color = client.put("/api/v1/admin/products/cr1016/colors", headers=headers, json={"colors": [{"code": "test", "label": "", "label_en": "Test", "is_default": True}]})
            self.assertEqual(422, empty_color.status_code, empty_color.text)
            self.assertTrue(product["colors"])

            duplicate = client.post("/api/v1/admin/products", headers=headers, json={"id": "cr1016", "name": "Duplicate", "title_name": "Duplicate"})
            self.assertEqual(409, duplicate.status_code, duplicate.text)

    def test_admin_catalog_v2_hierarchy_crud_and_conflicts(self) -> None:
        admin = create_user("catalog-v2-admin@example.com", None, "password123", role="admin", display_name="Catalog V2 Admin")
        headers = {"Authorization": "Bearer {}".format(create_session(admin)["token"])}
        root_id = "catalog-optional"
        inserted_root = False
        with get_connection() as database:
            if database.execute("SELECT 1 FROM categories WHERE id = ?", (root_id,)).fetchone() is None:
                database.execute(
                    """
                    INSERT INTO categories
                        (id, name, name_en, multiple, sort_order, parent_id,
                         catalog_type, enabled, version, translation_status)
                    VALUES (?, '可选配置', 'Optional Configurations', 1, 0,
                            NULL, 'optional', 1, 1, 'reviewed')
                    """,
                    (root_id,),
                )
                inserted_root = True
        category_id = None
        option_id = None
        option_2_id = None
        try:
            with TestClient(app) as client:
                category_response = client.post(
                    "/api/v1/admin/catalog/categories",
                    headers=headers,
                    json={
                        "parent_id": root_id,
                        "name_zh": "V2 测试分类",
                        "name_en": "V2 Test Category",
                        "translation_status": "reviewed",
                    },
                )
                self.assertEqual(201, category_response.status_code, category_response.text)
                category = category_response.json()
                category_id = category["id"]

                item_response = client.post(
                    "/api/v1/admin/catalog/items",
                    headers=headers,
                    json={
                        "category_id": category_id,
                        "code": "V2-REG-001",
                        "name_zh": "V2 测试配置",
                        "name_en": "V2 Test Option",
                        "price_cny": 100,
                        "price_usd": 15,
                        "translation_status": "reviewed",
                    },
                )
                self.assertEqual(201, item_response.status_code, item_response.text)
                option = item_response.json()
                option_id = option["id"]

                updated_response = client.patch(
                    "/api/v1/admin/catalog/items/{}".format(option_id),
                    headers=headers,
                    json={
                        "version": option["version"],
                        "category_id": category_id,
                        "code": option["code"],
                        "name_zh": "V2 测试配置已修改",
                        "name_en": option["name_en"],
                        "price_cny": 120,
                        "price_usd": 18,
                        "translation_status": "reviewed",
                    },
                )
                self.assertEqual(200, updated_response.status_code, updated_response.text)
                updated = updated_response.json()
                self.assertEqual("machine_draft", updated["translation_status"])

                second_response = client.post(
                    "/api/v1/admin/catalog/items",
                    headers=headers,
                    json={
                        "category_id": category_id,
                        "code": "V2-REG-002",
                        "name_zh": "V2 第二项",
                        "name_en": "V2 Second Option",
                        "price_cny": 0,
                        "price_usd": 0,
                        "translation_status": "reviewed",
                    },
                )
                self.assertEqual(201, second_response.status_code, second_response.text)
                second = second_response.json()
                option_2_id = second["id"]

                reordered = client.put(
                    "/api/v1/admin/catalog/items-order",
                    headers=headers,
                    json={
                        "category_id": category_id,
                        "items": [
                            {"id": second["id"], "version": second["version"]},
                            {"id": updated["id"], "version": updated["version"]},
                        ],
                    },
                )
                self.assertEqual(200, reordered.status_code, reordered.text)
                ordered_items = reordered.json()["items"]
                self.assertEqual([second["id"], updated["id"]], [item["id"] for item in ordered_items])
                second, updated = ordered_items

                catalog_tree = client.get("/api/v1/admin/catalog-tree", headers=headers)
                self.assertEqual(200, catalog_tree.status_code, catalog_tree.text)
                root = next(item for item in catalog_tree.json()["items"] if item["id"] == root_id)
                category_node = next(item for item in root["children"] if item["id"] == category_id)
                self.assertEqual([second["id"], updated["id"]], [item["id"] for item in category_node["options"]])

                stale_response = client.patch(
                    "/api/v1/admin/catalog/items/{}".format(option_id),
                    headers=headers,
                    json={
                        "version": option["version"],
                        "category_id": category_id,
                        "code": option["code"],
                        "name_zh": updated["name"],
                        "name_en": updated["name_en"],
                    },
                )
                self.assertEqual(409, stale_response.status_code, stale_response.text)
                self.assertEqual("CATALOG_VERSION_CONFLICT", stale_response.json()["error"]["code"])
                self.assertEqual(updated["version"], stale_response.json()["error"]["params"]["current_version"])

                delete_response = client.delete(
                    "/api/v1/admin/catalog/items/{}?version={}".format(option_id, updated["version"]),
                    headers=headers,
                )
                self.assertEqual(200, delete_response.status_code, delete_response.text)
                self.assertEqual("hard", delete_response.json()["mode"])
                option_id = None

                second_delete = client.delete(
                    "/api/v1/admin/catalog/items/{}?version={}".format(option_2_id, second["version"]),
                    headers=headers,
                )
                self.assertEqual(200, second_delete.status_code, second_delete.text)
                option_2_id = None

                self.assertEqual(
                    204,
                    client.delete(
                        "/api/v1/admin/catalog/categories/{}".format(category_id),
                        headers=headers,
                    ).status_code,
                )
                category_id = None
                protected = client.delete(
                    "/api/v1/admin/catalog/categories/{}".format(root_id),
                    headers=headers,
                )
                self.assertEqual(409, protected.status_code, protected.text)
                self.assertEqual("CATALOG_CATEGORY_PROTECTED", protected.json()["error"]["code"])
        finally:
            with get_connection() as database:
                if option_id:
                    database.execute("DELETE FROM options WHERE id = ?", (option_id,))
                if option_2_id:
                    database.execute("DELETE FROM options WHERE id = ?", (option_2_id,))
                if category_id:
                    database.execute("DELETE FROM categories WHERE id = ?", (category_id,))
                if inserted_root:
                    database.execute("DELETE FROM categories WHERE id = ?", (root_id,))

    def test_catalog_translation_draft_never_returns_partial_chinese(self) -> None:
        exact = translation_draft("共轨喷油器测试套件")
        self.assertTrue(exact["complete"])
        self.assertEqual("Common Rail Injector Test Kits", exact["draft"])
        preserved = translation_draft("BT618 Servo")
        self.assertTrue(preserved["complete"])
        self.assertEqual("BT618 Servo", preserved["draft"])
        unknown = translation_draft("尚未收录的中文内容")
        self.assertFalse(unknown["complete"])
        self.assertEqual("", unknown["draft"])

    def test_catalog_request_validation_uses_a_stable_error_object(self) -> None:
        admin = create_user("catalog-validation@example.com", None, "password123", role="admin", display_name="Catalog Validation")
        headers = {"Authorization": "Bearer {}".format(create_session(admin)["token"])}
        with TestClient(app) as client:
            response = client.post("/api/v1/admin/catalog/items", headers=headers, json={})
        self.assertEqual(422, response.status_code, response.text)
        self.assertEqual("CATALOG_VALIDATION_FAILED", response.json()["error"]["code"])
        self.assertIsInstance(response.json()["detail"], str)

    def test_service_tool_catalog_and_independent_cart_workflow(self) -> None:
        root_id = "catalog-tools"
        inserted_root = False
        with get_connection() as database:
            if database.execute("SELECT 1 FROM categories WHERE id = ?", (root_id,)).fetchone() is None:
                database.execute(
                    """
                    INSERT INTO categories
                        (id, name, name_en, multiple, sort_order, parent_id,
                         catalog_type, enabled, version, translation_status)
                    VALUES (?, '维修工具', 'Service Tools', 1, 1, NULL,
                            'tools', 1, 1, 'reviewed')
                    """,
                    (root_id,),
                )
                inserted_root = True
        option = create_catalog_item(
            category_id=root_id,
            code="TOOL-REG-001",
            name_zh="回归测试工具",
            name_en="Regression Test Tool",
            price_cny=200,
            price_usd=30,
            translation_status="reviewed",
        )
        customer = create_user("tool-cart@example.com", None, "password123", display_name="Tool Cart")
        headers = {"Authorization": "Bearer {}".format(create_session(customer)["token"])}
        saved_id = None
        try:
            with TestClient(app) as client:
                public = client.get("/api/v1/catalog/items?type=tools&lang=en")
                self.assertEqual(200, public.status_code, public.text)
                self.assertIn(option["id"], {item["id"] for item in public.json()["items"]})
                self.assertNotIn("price_cny_minor", public.text)
                self.assertNotIn("price_usd_minor", public.text)

                created_response = client.post(
                    "/api/v1/cart/catalog-items",
                    headers=headers,
                    json={"option_id": option["id"], "quantity": 2, "lang": "en"},
                )
                self.assertEqual(201, created_response.status_code, created_response.text)
                saved = created_response.json()
                saved_id = saved["id"]
                self.assertEqual("tools", saved["catalog_type"])
                self.assertEqual("Regression Test Tool", saved["name"])
                self.assertNotIn("price_cny_minor", saved)
                self.assertNotIn("price_usd_minor", saved)

                updated_response = client.patch(
                    "/api/v1/cart/catalog-items/{}".format(saved_id),
                    headers=headers,
                    json={"version": saved["version"], "quantity": 4, "lang": "zh"},
                )
                self.assertEqual(200, updated_response.status_code, updated_response.text)
                updated = updated_response.json()
                self.assertEqual(4, updated["quantity"])
                self.assertEqual("回归测试工具", updated["name"])

                stale = client.patch(
                    "/api/v1/cart/catalog-items/{}".format(saved_id),
                    headers=headers,
                    json={"version": saved["version"], "quantity": 5},
                )
                self.assertEqual(409, stale.status_code, stale.text)
                self.assertEqual("CATALOG_CART_VERSION_CONFLICT", stale.json()["error"]["code"])

                set_quantity = client.put(
                    "/api/v1/cart/catalog-options/{}".format(option["id"]),
                    headers=headers,
                    json={"quantity": 7, "lang": "en"},
                )
                self.assertEqual(200, set_quantity.status_code, set_quantity.text)
                self.assertEqual(7, set_quantity.json()["quantity"])

                duplicate = client.post(
                    "/api/v1/cart/catalog-items",
                    headers=headers,
                    json={"option_id": option["id"], "quantity": 2, "lang": "en"},
                )
                self.assertEqual(201, duplicate.status_code, duplicate.text)
                consolidated = client.put(
                    "/api/v1/cart/catalog-options/{}".format(option["id"]),
                    headers=headers,
                    json={"quantity": 3, "lang": "zh"},
                )
                self.assertEqual(200, consolidated.status_code, consolidated.text)
                active_items = client.get("/api/v1/cart/catalog-items", headers=headers).json()["items"]
                self.assertEqual(1, len(active_items))
                self.assertEqual(3, active_items[0]["quantity"])

                removed = client.put(
                    "/api/v1/cart/catalog-options/{}".format(option["id"]),
                    headers=headers,
                    json={"quantity": 0, "lang": "zh"},
                )
                self.assertEqual(204, removed.status_code, removed.text)
                self.assertEqual([], client.get("/api/v1/cart/catalog-items", headers=headers).json()["items"])
        finally:
            with get_connection() as database:
                database.execute("DELETE FROM saved_catalog_items WHERE option_id = ?", (option["id"],))
                database.execute("DELETE FROM options WHERE id = ?", (option["id"],))
                if inserted_root:
                    database.execute("DELETE FROM categories WHERE id = ?", (root_id,))

    def test_mixed_cart_share_quote_pdf_and_atomic_archive(self) -> None:
        roots = {
            "catalog-tools": ("维修工具", "Service Tools", "tools"),
            "catalog-accessories": ("设备附件", "Accessories", "accessories"),
        }
        inserted_roots = []
        with get_connection() as database:
            for root_id, (name_zh, name_en, catalog_type) in roots.items():
                if database.execute("SELECT 1 FROM categories WHERE id = ?", (root_id,)).fetchone() is None:
                    database.execute(
                        """
                        INSERT INTO categories
                            (id, name, name_en, multiple, sort_order, parent_id,
                             catalog_type, enabled, version, translation_status)
                        VALUES (?, ?, ?, 1, 1, NULL, ?, 1, 1, 'reviewed')
                        """,
                        (root_id, name_zh, name_en, catalog_type),
                    )
                    inserted_roots.append(root_id)

        tool = create_catalog_item(
            category_id="catalog-tools", code="MIX-TOOL-001",
            name_zh="混合测试工具", name_en="Mixed Test Tool",
            price_cny=120, price_usd=18, translation_status="reviewed",
        )
        accessory = create_catalog_item(
            category_id="catalog-accessories", code="MIX-ACC-001",
            name_zh="混合测试附件", name_en="Mixed Test Accessory",
            price_cny=80, price_usd=12, translation_status="reviewed",
        )
        customer = create_user("mixed-cart@example.com", None, "password123", display_name="Mixed Customer")
        other = create_user("mixed-other@example.com", None, "password123", display_name="Other Customer")
        staff = create_user("mixed-sales@example.com", None, "password123", role="sales", display_name="Mixed Sales")
        admin = create_user("mixed-admin@example.com", None, "password123", role="admin", display_name="Mixed Admin")
        product = get_product("cr1016")
        snapshot = build_snapshot(product["id"], product["colors"][0]["code"], {}, "zh")
        config = save_config(customer["id"], "Mixed Device", product["id"], snapshot)
        other_config = save_config(other["id"], "Other Device", product["id"], snapshot)
        customer_headers = {"Authorization": "Bearer {}".format(create_session(customer)["token"])}
        other_headers = {"Authorization": "Bearer {}".format(create_session(other)["token"])}
        staff_headers = {"Authorization": "Bearer {}".format(create_session(staff)["token"])}
        admin_headers = {"Authorization": "Bearer {}".format(create_session(admin)["token"])}
        saved_ids = []
        share_id = None
        quote_id = None
        catalog_quote_id = None
        try:
            with TestClient(app) as client:
                for option, quantity in ((tool, 2), (accessory, 3)):
                    response = client.post(
                        "/api/v1/cart/catalog-items", headers=customer_headers,
                        json={"option_id": option["id"], "quantity": quantity, "lang": "zh"},
                    )
                    self.assertEqual(201, response.status_code, response.text)
                    saved_ids.append(response.json()["id"])

                refs = [
                    {"item_type": "accessory", "id": saved_ids[1]},
                    {"item_type": "device_config", "id": config["id"]},
                    {"item_type": "tool", "id": saved_ids[0]},
                ]
                denied = client.post(
                    "/api/v1/cart/batch-archive", headers=customer_headers,
                    json={"items": refs + [{"item_type": "device_config", "id": other_config["id"]}]},
                )
                self.assertEqual(403, denied.status_code, denied.text)
                self.assertEqual(1, len(client.get("/api/v1/configs", headers=customer_headers).json()["items"]))
                self.assertEqual(2, len(client.get("/api/v1/cart/catalog-items", headers=customer_headers).json()["items"]))

                direct_pdf = client.post(
                    "/api/v1/cart/export/pdf", headers=customer_headers,
                    json={"items": refs, "lang": "en"},
                )
                self.assertEqual(200, direct_pdf.status_code, direct_pdf.text)
                self.assertEqual("application/pdf", direct_pdf.headers["content-type"])
                self.assertGreater(len(direct_pdf.content), 100)
                from pypdf import PdfReader
                customer_pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(direct_pdf.content)).pages)
                self.assertNotIn("Reference Price", customer_pdf_text)
                self.assertNotIn("Device Base Price", customer_pdf_text)

                accessory_only_pdf = client.post(
                    "/api/v1/cart/export/pdf", headers=customer_headers,
                    json={"items": [{"item_type": "accessory", "id": saved_ids[1]}], "lang": "zh"},
                )
                self.assertEqual(200, accessory_only_pdf.status_code, accessory_only_pdf.text)
                self.assertGreater(len(accessory_only_pdf.content), 100)

                catalog_only = client.post(
                    "/api/v1/cart/share", headers=customer_headers,
                    json={"items": [{"item_type": "tool", "id": saved_ids[0]}], "lang": "en"},
                )
                self.assertEqual(201, catalog_only.status_code, catalog_only.text)
                self.assertIsNone(catalog_only.json()["config_id"])
                self.assertEqual(1, catalog_only.json()["item_count"])
                catalog_only_code = catalog_only.json()["code"]
                catalog_preview = client.get(
                    "/api/v1/staff/shares/{}/preview?lang=en".format(catalog_only_code),
                    headers=staff_headers,
                )
                self.assertEqual(200, catalog_preview.status_code, catalog_preview.text)
                self.assertEqual(["tool"], [item["item_type"] for item in catalog_preview.json()["items"]])

                catalog_quote = client.post(
                    "/api/v1/quotes", headers=staff_headers,
                    json={
                        "source_share_id": catalog_only.json()["id"],
                        "title": "Tools Only Quotation",
                        "language": "en",
                        "items": [{"kind": "tool", "code": "MIX-TOOL-001", "name": "Mixed Test Tool", "quantity": 2, "price": 18}],
                        "currency": "USD",
                    },
                )
                self.assertEqual(201, catalog_quote.status_code, catalog_quote.text)
                catalog_quote_id = catalog_quote.json()["id"]

                accessory_only = client.post(
                    "/api/v1/cart/share", headers=customer_headers,
                    json={"items": [{"item_type": "accessory", "id": saved_ids[1]}], "lang": "zh"},
                )
                self.assertEqual(201, accessory_only.status_code, accessory_only.text)
                self.assertIsNone(accessory_only.json()["config_id"])
                self.assertEqual(1, accessory_only.json()["item_count"])

                shared = client.post(
                    "/api/v1/cart/share", headers=customer_headers,
                    json={"items": refs, "lang": "zh"},
                )
                self.assertEqual(201, shared.status_code, shared.text)
                share_id = shared.json()["id"]
                self.assertEqual(3, shared.json()["item_count"])
                code = shared.json()["code"]
                search_result = search_all_shares(query="混合测试工具")
                self.assertIn(share_id, {item["id"] for item in search_result["items"]})
                shared_summary = next(item for item in search_result["items"] if item["id"] == share_id)
                self.assertEqual(1, shared_summary["device_count"])
                self.assertEqual(2, shared_summary["tool_quantity"])
                self.assertEqual(3, shared_summary["accessory_quantity"])
                staff_share_list = client.get(
                    "/api/v1/admin/shares?query=混合测试工具&status=active",
                    headers=staff_headers,
                )
                self.assertEqual(200, staff_share_list.status_code, staff_share_list.text)
                self.assertIn(share_id, {item["id"] for item in staff_share_list.json()["items"]})

                closed_share = client.patch(
                    "/api/v1/admin/shares/{}/status".format(share_id), headers=admin_headers,
                    json={"active": False},
                )
                self.assertEqual(200, closed_share.status_code, closed_share.text)
                reopened_share = client.patch(
                    "/api/v1/admin/shares/{}/status".format(share_id), headers=admin_headers,
                    json={"active": True},
                )
                self.assertEqual(200, reopened_share.status_code, reopened_share.text)

                preview = client.get(
                    "/api/v1/staff/shares/{}/preview?lang=en".format(code),
                    headers=staff_headers,
                )
                self.assertEqual(200, preview.status_code, preview.text)
                preview_json = preview.json()
                self.assertEqual(2, preview_json["document_version"])
                self.assertEqual({"device_config", "tool", "accessory"}, {item["item_type"] for item in preview_json["items"]})
                self.assertEqual(["device_config", "tool", "accessory"], [item["item_type"] for item in preview_json["items"]])
                device_item = next(item for item in preview_json["items"] if item["item_type"] == "device_config")
                self.assertIn("CNY", device_item["pricing_by_currency"])
                self.assertIn("USD", device_item["pricing_by_currency"])

                customer_preview = client.get(
                    "/api/v1/customer/shares/{}?lang=en".format(code),
                    headers=other_headers,
                )
                self.assertEqual(200, customer_preview.status_code, customer_preview.text)
                customer_preview_json = customer_preview.json()
                self.assertEqual(3, customer_preview_json["available_count"])
                self.assertNotIn("sender_email", customer_preview_json)
                self.assertNotIn("pricing", str(customer_preview_json).lower())
                imported = client.post(
                    "/api/v1/customer/shares/{}/import".format(code),
                    headers=other_headers,
                    json={"idempotency_key": "mixed-share-import-0001", "lang": "en"},
                )
                self.assertEqual(200, imported.status_code, imported.text)
                self.assertEqual(3, imported.json()["imported_count"])
                replayed = client.post(
                    "/api/v1/customer/shares/{}/import".format(code),
                    headers=other_headers,
                    json={"idempotency_key": "mixed-share-import-0001", "lang": "en"},
                )
                self.assertEqual(200, replayed.status_code, replayed.text)
                self.assertTrue(replayed.json()["replayed"])
                self.assertEqual(2, len(client.get("/api/v1/configs", headers=other_headers).json()["items"]))
                self.assertEqual(2, len(client.get("/api/v1/cart/catalog-items", headers=other_headers).json()["items"]))

                with get_connection() as database:
                    database.execute("UPDATE options SET enabled = 0 WHERE id = ?", (tool["id"],))
                stale_preview = client.get(
                    "/api/v1/customer/shares/{}?lang=zh".format(code),
                    headers=other_headers,
                )
                self.assertEqual(200, stale_preview.status_code, stale_preview.text)
                stale_tool = next(item for item in stale_preview.json()["items"] if item["item_type"] == "tool")
                self.assertFalse(stale_tool["available"])
                self.assertTrue(stale_tool["missing"])
                partial_import = client.post(
                    "/api/v1/customer/shares/{}/import".format(code),
                    headers=other_headers,
                    json={"idempotency_key": "mixed-share-import-partial-0002", "lang": "zh"},
                )
                self.assertEqual(200, partial_import.status_code, partial_import.text)
                self.assertEqual(2, partial_import.json()["imported_count"])
                self.assertEqual(1, partial_import.json()["skipped_count"])
                self.assertEqual("tool", partial_import.json()["skipped"][0]["item_type"])
                with get_connection() as database:
                    database.execute("UPDATE options SET enabled = 1 WHERE id = ?", (tool["id"],))

                exported = client.get(
                    "/api/v1/shares/{}/pdf?lang=en".format(code), headers=staff_headers,
                )
                self.assertEqual(200, exported.status_code, exported.text)
                self.assertEqual("application/pdf", exported.headers["content-type"])
                self.assertGreater(len(exported.content), 100)
                staff_pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(exported.content)).pages)
                self.assertIn("Reference Price", staff_pdf_text)

                quote = client.post(
                    "/api/v1/quotes", headers=staff_headers,
                    json={
                        "config_id": config["id"], "source_share_id": share_id,
                        "title": "Mixed Quotation", "language": "en",
                        "customer_name": "Mixed Customer", "customer_email": "mixed-cart@example.com",
                        "items": [
                            {"kind": "product", "code": "CR1016", "name": "Test Bench", "quantity": 1, "price": 1000},
                            {"kind": "tool", "code": "MIX-TOOL-001", "name": "Mixed Test Tool", "quantity": 2, "price": 18},
                        ],
                        "total_price": 0, "currency": "USD",
                    },
                )
                self.assertEqual(201, quote.status_code, quote.text)
                quote_id = quote.json()["id"]
                self.assertEqual(2, quote.json()["document_version"])
                self.assertEqual(1036, quote.json()["total_price"])
                quote_pdf_response = client.get("/api/v1/quotes/{}/pdf".format(quote_id), headers=staff_headers)
                self.assertEqual(200, quote_pdf_response.status_code, quote_pdf_response.text)
                self.assertGreater(len(quote_pdf_response.content), 100)

                own_shares = client.get("/api/v1/customer/me/shares", headers=customer_headers)
                self.assertEqual(200, own_shares.status_code, own_shares.text)
                self.assertIn(share_id, {item["id"] for item in own_shares.json()["items"]})
                own_share = client.get(
                    "/api/v1/customer/me/shares/{}?lang=en".format(share_id),
                    headers=customer_headers,
                )
                self.assertEqual(200, own_share.status_code, own_share.text)
                self.assertNotIn("pricing", str(own_share.json()).lower())

                delivered = client.post(
                    "/api/v1/staff/quotes/{}/deliver".format(quote_id),
                    headers=staff_headers,
                    json={"source_share_id": share_id},
                )
                self.assertEqual(200, delivered.status_code, delivered.text)
                self.assertEqual(customer["id"], delivered.json()["recipient_user_id"])
                customer_quotes = client.get("/api/v1/customer/me/quotes", headers=customer_headers)
                self.assertEqual(200, customer_quotes.status_code, customer_quotes.text)
                self.assertEqual(1, customer_quotes.json()["unread_count"])
                customer_quote = client.get(
                    "/api/v1/customer/me/quotes/{}".format(quote_id), headers=customer_headers,
                )
                self.assertEqual(200, customer_quote.status_code, customer_quote.text)
                self.assertEqual(1036, customer_quote.json()["total_price"])
                denied_quote = client.get(
                    "/api/v1/customer/me/quotes/{}".format(quote_id), headers=other_headers,
                )
                self.assertEqual(404, denied_quote.status_code, denied_quote.text)
                customer_quote_pdf = client.get(
                    "/api/v1/customer/me/quotes/{}/pdf".format(quote_id), headers=customer_headers,
                )
                self.assertEqual(200, customer_quote_pdf.status_code, customer_quote_pdf.text)
                withdrawn = client.post(
                    "/api/v1/staff/quotes/{}/withdraw".format(quote_id),
                    headers=staff_headers,
                    json={"recipient_user_id": customer["id"]},
                )
                self.assertEqual(200, withdrawn.status_code, withdrawn.text)
                self.assertEqual([], client.get("/api/v1/customer/me/quotes", headers=customer_headers).json()["items"])

                archived = client.post(
                    "/api/v1/cart/batch-archive", headers=customer_headers,
                    json={"items": refs, "lang": "zh"},
                )
                self.assertEqual(200, archived.status_code, archived.text)
                self.assertEqual(3, archived.json()["archived_count"])
                self.assertEqual([], client.get("/api/v1/configs", headers=customer_headers).json()["items"])
                self.assertEqual([], client.get("/api/v1/cart/catalog-items", headers=customer_headers).json()["items"])
        finally:
            with get_connection() as database:
                if quote_id:
                    database.execute("DELETE FROM commerce_quotes WHERE id = ?", (quote_id,))
                if catalog_quote_id:
                    database.execute("DELETE FROM commerce_quotes WHERE id = ?", (catalog_quote_id,))
                database.execute("DELETE FROM quote_deliveries WHERE recipient_user_id IN (?, ?)", (customer["id"], other["id"]))
                database.execute("DELETE FROM commerce_shares WHERE created_by = ?", (customer["id"],))
                database.execute("DELETE FROM share_imports WHERE user_id = ?", (other["id"],))
                database.execute("DELETE FROM saved_catalog_items WHERE user_id IN (?, ?)", (customer["id"], other["id"]))
                database.execute("DELETE FROM saved_configs WHERE user_id IN (?, ?)", (customer["id"], other["id"]))
                database.execute("DELETE FROM options WHERE id IN (?, ?)", (tool["id"], accessory["id"]))
                for root_id in inserted_roots:
                    database.execute("DELETE FROM categories WHERE id = ?", (root_id,))

    def test_customer_inquiries_are_separate_from_shares_and_hide_prices(self) -> None:
        customer = create_user("inquiry-customer@example.com", None, "password123", display_name="Inquiry Customer")
        product = get_product("cr1016")
        snapshot = build_snapshot(product["id"], product["colors"][0]["code"], {}, "zh")
        config = save_config(customer["id"], "Inquiry Cart Device", product["id"], snapshot)
        headers = {"Authorization": "Bearer {}".format(create_session(customer)["token"])}
        try:
            with TestClient(app) as client:
                current = client.post(
                    "/api/v1/customer/inquiries/current-configuration", headers=headers,
                    json={
                        "product_id": product["id"], "color": product["colors"][0]["code"],
                        "selections": {}, "lang": "zh", "message": "请联系我", "idempotency_key": "current-inquiry-0001",
                    },
                )
                self.assertEqual(201, current.status_code, current.text)
                current_payload = current.json()
                self.assertEqual("current_device", current_payload["source_type"])
                self.assertEqual(1, current_payload["item_count"])
                self.assertNotIn("pricing", str(current_payload).lower())

                replay = client.post(
                    "/api/v1/customer/inquiries/current-configuration", headers=headers,
                    json={
                        "product_id": product["id"], "color": product["colors"][0]["code"],
                        "selections": {}, "lang": "zh", "message": "请联系我", "idempotency_key": "current-inquiry-0001",
                    },
                )
                self.assertEqual(201, replay.status_code, replay.text)
                self.assertEqual(current_payload["id"], replay.json()["id"])
                self.assertTrue(replay.json()["replayed"])

                cart = client.post(
                    "/api/v1/customer/inquiries/cart", headers=headers,
                    json={"lang": "en", "message": "Cart inquiry", "idempotency_key": "cart-inquiry-000001"},
                )
                self.assertEqual(201, cart.status_code, cart.text)
                self.assertEqual("cart", cart.json()["source_type"])
                self.assertEqual(1, cart.json()["item_count"])

                own = client.get("/api/v1/customer/me/inquiries", headers=headers)
                self.assertEqual(200, own.status_code, own.text)
                self.assertEqual(2, own.json()["total"])
                detail = client.get("/api/v1/customer/me/inquiries/{}?lang=en".format(cart.json()["id"]), headers=headers)
                self.assertEqual(200, detail.status_code, detail.text)
                self.assertEqual("device_config", detail.json()["items"][0]["item_type"])
                self.assertNotIn("price", str(detail.json()).lower())

                cancelled = client.post(
                    "/api/v1/customer/me/inquiries/{}/cancel".format(cart.json()["id"]),
                    headers=headers, json={"version": cart.json()["version"]},
                )
                self.assertEqual(200, cancelled.status_code, cancelled.text)
                self.assertEqual("cancelled", cancelled.json()["status"])
        finally:
            with get_connection() as database:
                database.execute("DELETE FROM customer_inquiries WHERE created_by = ?", (customer["id"],))
                database.execute("DELETE FROM saved_configs WHERE id = ?", (config["id"],))
                database.execute("DELETE FROM users WHERE id = ?", (customer["id"],))

    def test_staff_can_assign_and_convert_an_inquiry_to_a_draft_quote(self) -> None:
        customer = create_user("inquiry-staff-customer@example.com", None, "password123", display_name="Inquiry Staff Customer")
        sales = create_user("inquiry-staff-sales@example.com", None, "password123", role="sales", display_name="Inquiry Staff Sales")
        product = get_product("cr1016")
        customer_headers = {"Authorization": "Bearer {}".format(create_session(customer)["token"])}
        sales_headers = {"Authorization": "Bearer {}".format(create_session(sales)["token"])}
        quote_id = None
        inquiry_id = None
        try:
            with TestClient(app) as client:
                created = client.post(
                    "/api/v1/customer/inquiries/current-configuration", headers=customer_headers,
                    json={"product_id": product["id"], "color": product["colors"][0]["code"], "selections": {}, "lang": "zh", "message": "Need sales follow-up", "idempotency_key": "staff-inquiry-000001"},
                )
                self.assertEqual(201, created.status_code, created.text)
                inquiry_id = created.json()["id"]

                listing = client.get("/api/v1/staff/inquiries?status=new", headers=sales_headers)
                self.assertEqual(200, listing.status_code, listing.text)
                listed = next(item for item in listing.json()["items"] if item["id"] == inquiry_id)
                self.assertEqual("new", listed["status"])

                assigned = client.patch(
                    "/api/v1/staff/inquiries/{}".format(inquiry_id), headers=sales_headers,
                    json={"version": listed["version"], "status": "assigned", "assigned_to": sales["id"]},
                )
                self.assertEqual(200, assigned.status_code, assigned.text)
                self.assertEqual(sales["id"], assigned.json()["assigned_to"])

                converted = client.post(
                    "/api/v1/staff/inquiries/{}/convert-to-quote".format(inquiry_id), headers=sales_headers,
                    json={"version": assigned.json()["version"], "currency": "CNY"},
                )
                self.assertEqual(201, converted.status_code, converted.text)
                self.assertEqual("quoted", converted.json()["inquiry"]["status"])
                self.assertTrue(converted.json()["quote"]["items"])
                quote_id = converted.json()["quote"]["id"]
        finally:
            with get_connection() as database:
                if quote_id:
                    database.execute("DELETE FROM commerce_quotes WHERE id = ?", (quote_id,))
                if inquiry_id:
                    database.execute("DELETE FROM customer_inquiries WHERE id = ?", (inquiry_id,))
                database.execute("DELETE FROM users WHERE id IN (?, ?)", (customer["id"], sales["id"]))

    def test_staff_can_archive_restore_and_review_quote_history(self) -> None:
        customer = create_user("quote-history-customer@example.com", None, "password123", display_name="Quote History Customer")
        sales = create_user("quote-history-sales@example.com", None, "password123", role="sales", display_name="Quote History Sales")
        customer_headers = {"Authorization": "Bearer {}".format(create_session(customer)["token"])}
        sales_headers = {"Authorization": "Bearer {}".format(create_session(sales)["token"])}
        quote_id = None
        try:
            with TestClient(app) as client:
                created = client.post(
                    "/api/v1/quotes", headers=sales_headers,
                    json={"title": "Lifecycle quote", "items": [{"kind": "product", "code": "CR1016", "name": "Test bench", "quantity": 1, "price": 100}], "total_price": 0, "currency": "USD"},
                )
                self.assertEqual(201, created.status_code, created.text)
                quote_id = created.json()["id"]

                delivered = client.post(
                    "/api/v1/staff/quotes/{}/deliver".format(quote_id), headers=sales_headers,
                    json={"recipient_user_id": customer["id"]},
                )
                self.assertEqual(200, delivered.status_code, delivered.text)

                sent = client.get("/api/v1/quotes/{}".format(quote_id), headers=sales_headers)
                self.assertEqual("sent", sent.json()["lifecycle_status"])
                archived = client.post(
                    "/api/v1/staff/quotes/{}/archive".format(quote_id), headers=sales_headers,
                    json={"version": sent.json()["version"]},
                )
                self.assertEqual(200, archived.status_code, archived.text)
                self.assertEqual("archived", archived.json()["lifecycle_status"])

                blocked = client.post(
                    "/api/v1/quotes", headers=sales_headers,
                    json={"quote_id": quote_id, "title": "Blocked", "items": [{"kind": "product", "name": "Test", "quantity": 1, "price": 1}], "total_price": 1},
                )
                self.assertEqual(409, blocked.status_code, blocked.text)
                history = client.get("/api/v1/staff/quotes/{}/history".format(quote_id), headers=sales_headers)
                self.assertEqual(200, history.status_code, history.text)
                self.assertEqual(1, len(history.json()["revisions"]))
                self.assertEqual(1, len(history.json()["deliveries"]))

                restored = client.post(
                    "/api/v1/staff/quotes/{}/restore".format(quote_id), headers=sales_headers,
                    json={"version": archived.json()["version"]},
                )
                self.assertEqual(200, restored.status_code, restored.text)
                self.assertEqual("sent", restored.json()["lifecycle_status"])
                self.assertEqual(200, client.get("/api/v1/customer/me/quotes/{}".format(quote_id), headers=customer_headers).status_code)
        finally:
            with get_connection() as database:
                if quote_id:
                    database.execute("DELETE FROM quote_deliveries WHERE quote_id = ?", (quote_id,))
                    database.execute("DELETE FROM commerce_quotes WHERE id = ?", (quote_id,))
                database.execute("DELETE FROM users WHERE id IN (?, ?)", (customer["id"], sales["id"]))

    def test_catalog_manager_permissions_and_atomic_product_save(self) -> None:
        admin = create_user("catalog-admin@example.com", None, "password123", role="admin", display_name="Catalog Admin")
        sales = create_user("catalog-sales@example.com", None, "password123", role="sales", display_name="Catalog Sales")
        admin_headers = {"Authorization": "Bearer {}".format(create_session(admin)["token"])}
        sales_headers = {"Authorization": "Bearer {}".format(create_session(sales)["token"])}
        with TestClient(app) as client:
            self.assertEqual(200, client.get("/api/v1/admin/products", headers=sales_headers).status_code)
            self.assertEqual(200, client.get("/api/v1/admin/config-catalog", headers=sales_headers).status_code)
            self.assertEqual(403, client.get("/api/v1/admin/users", headers=sales_headers).status_code)
            self.assertEqual(403, client.get("/api/v1/admin/audit-logs", headers=sales_headers).status_code)

            product = client.get("/api/v1/admin/products/cr1016", headers=admin_headers).json()
            selected = [option["id"] for category in product["categories"] for option in category["options"] if option["selected"]]
            payload = {
                "name": product["name"],
                "description": "Atomic product description",
                "title_name": product["title_name"],
                "colors": product["colors"],
                "option_ids": selected,
                "option_overrides": {},
            }
            saved = client.put("/api/v1/admin/products/cr1016/configuration", headers=admin_headers, json=payload)
            self.assertEqual(200, saved.status_code, saved.text)
            self.assertEqual("Atomic product description", saved.json()["description"])

            failed = client.put("/api/v1/admin/products/cr1016/configuration", headers=admin_headers, json={**payload, "description": "Must roll back", "option_ids": []})
            self.assertEqual(422, failed.status_code, failed.text)
            self.assertEqual("Atomic product description", client.get("/api/v1/admin/products/cr1016", headers=admin_headers).json()["description"])

    def test_admin_cannot_disable_self(self) -> None:
        admin = create_user("self-guard@example.com", None, "password123", role="admin", display_name="Self Guard")
        headers = {"Authorization": "Bearer {}".format(create_session(admin)["token"])}
        with TestClient(app) as client:
            response = client.patch("/api/v1/admin/users/{}/status".format(admin["id"]), headers=headers, json={"enabled": False, "version": admin["version"]})
            audit_items = client.get("/api/v1/admin/audit-logs", headers=headers).json()["items"]
        self.assertEqual(422, response.status_code)
        failure = next(item for item in audit_items if item["entity_id"] == admin["id"] and item["action"] == "PATCH_failed")
        self.assertEqual("ACCOUNT_SELF_DISABLE_FORBIDDEN", failure["details"]["error_code"])
        self.assertTrue(failure["details"]["request_id"])

    def test_admin_account_edit_validation_and_password_reset(self) -> None:
        admin = create_user("account-guard@example.com", None, "password123", role="admin", display_name="Account Guard")
        customer = create_user("account-customer@example.com", "+861590000091", "password123", display_name="Account Customer")
        admin_token = create_session(admin)["token"]
        customer_token = create_session(customer)["token"]
        headers = {"Authorization": "Bearer {}".format(admin_token)}
        with TestClient(app) as client:
            invalid = client.post("/api/v1/admin/users", headers=headers, json={"display_name": "Invalid", "email": "invalid", "password": "password123", "role": "customer"})
            self.assertEqual(422, invalid.status_code, invalid.text)
            renamed = client.patch("/api/v1/admin/users/{}".format(admin["id"]), headers=headers, json={"display_name": "Renamed admin", "version": admin["version"]})
            self.assertEqual(200, renamed.status_code, renamed.text)
            reset = client.patch("/api/v1/admin/users/{}/password".format(customer["id"]), headers=headers, json={"password": "newpassword123", "version": customer["version"]})
            self.assertEqual(200, reset.status_code, reset.text)
            self.assertEqual(401, client.get("/api/v1/auth/me", headers={"Authorization": "Bearer {}".format(customer_token)}).status_code)
            self.assertIsNotNone(authenticate("account-customer@example.com", "newpassword123"))

    def test_admin_account_lifecycle_filters_and_structured_errors(self) -> None:
        admin = create_user("lifecycle-admin@example.com", None, "password123", role="admin", display_name="Lifecycle Admin")
        target = create_user("lifecycle-target@example.com", "+861590000093", "password123", display_name="Lifecycle Target", phone_country="CN")
        target_token = create_session(target)["token"]
        headers = {"Authorization": "Bearer {}".format(create_session(admin)["token"]), "X-UI-Language": "en"}
        with TestClient(app) as client:
            cleared = client.patch(
                "/api/v1/admin/users/{}".format(target["id"]), headers=headers,
                json={"email": None, "version": target["version"]},
            )
            self.assertEqual(200, cleared.status_code, cleared.text)
            self.assertIsNone(cleared.json()["email"])
            self.assertEqual(401, client.get("/api/v1/auth/me", headers={"Authorization": "Bearer {}".format(target_token)}).status_code)

            no_contact = client.patch(
                "/api/v1/admin/users/{}".format(target["id"]), headers=headers,
                json={"phone": None, "version": cleared.json()["version"]},
            )
            self.assertEqual(422, no_contact.status_code, no_contact.text)
            self.assertEqual("ACCOUNT_CONTACT_REQUIRED", no_contact.json()["error"]["code"])
            self.assertTrue(no_contact.json()["request_id"])
            self.assertEqual("ACCOUNT_CONTACT_REQUIRED", no_contact.headers["x-error-code"])

            archived = client.post(
                "/api/v1/admin/users/{}/archive".format(target["id"]), headers=headers,
                json={"reason": "duplicate account", "version": cleared.json()["version"]},
            )
            self.assertEqual(200, archived.status_code, archived.text)
            self.assertTrue(archived.json()["archived"])
            active_list = client.get("/api/v1/admin/users?q=Lifecycle%20Target", headers=headers).json()
            self.assertEqual(0, active_list["total"])
            archived_list = client.get("/api/v1/admin/users?archived=true&q=Lifecycle%20Target", headers=headers).json()
            self.assertEqual(1, archived_list["total"])

            restored = client.post(
                "/api/v1/admin/users/{}/restore".format(target["id"]), headers=headers,
                json={"version": archived.json()["version"]},
            )
            self.assertEqual(200, restored.status_code, restored.text)
            self.assertFalse(restored.json()["archived"])
            self.assertTrue(restored.json()["enabled"])
            actions = {item["action"] for item in client.get("/api/v1/admin/audit-logs", headers=headers).json()["items"] if item["entity_id"] == target["id"]}
            self.assertTrue({"account_update", "account_archive", "account_restore"}.issubset(actions))

    def test_admin_can_create_each_role_and_duplicates_identify_the_field(self) -> None:
        admin = create_user("create-role-admin@example.com", None, "password123", role="admin", display_name="Create Role Admin")
        headers = {"Authorization": "Bearer {}".format(create_session(admin)["token"])}
        created = []
        with TestClient(app) as client:
            for role in ("customer", "sales", "admin"):
                response = client.post("/api/v1/admin/users", headers=headers, json={"display_name": "Created {}".format(role), "email": "created-{}@example.com".format(role), "password": "password123", "role": role})
                self.assertEqual(201, response.status_code, response.text)
                self.assertEqual(role, response.json()["role"])
                created.append(response.json())
            duplicate = client.post("/api/v1/admin/users", headers=headers, json={"display_name": "Duplicate", "email": "CREATED-SALES@example.com", "password": "password123", "role": "sales"})
            self.assertEqual(409, duplicate.status_code, duplicate.text)
            self.assertEqual("ACCOUNT_EMAIL_DUPLICATE", duplicate.json()["error"]["code"])
            self.assertEqual("email", duplicate.json()["error"]["field"])

    def test_account_archive_preserves_saved_configuration_and_share(self) -> None:
        admin = create_user("history-admin@example.com", None, "password123", role="admin", display_name="History Admin")
        owner = create_user("history-owner@example.com", None, "password123", display_name="History Owner")
        product = get_product("cr1016")
        saved = save_config(owner["id"], "Archived owner configuration", product["id"], build_snapshot(product["id"], product["colors"][0]["code"], {}))
        share = create_share(saved["id"], owner["id"])
        headers = {"Authorization": "Bearer {}".format(create_session(admin)["token"])}
        with TestClient(app) as client:
            archived = client.post("/api/v1/admin/users/{}/archive".format(owner["id"]), headers=headers, json={"reason": "history test", "version": owner["version"]})
            self.assertEqual(200, archived.status_code, archived.text)
        self.assertTrue(any(item["id"] == saved["id"] for item in list_saved_configs(owner["id"])))
        self.assertEqual(saved["id"], get_share(share["code"])["config_id"])

    def test_admin_account_optimistic_lock_and_session_policy(self) -> None:
        admin = create_user("version-admin@example.com", None, "password123", role="admin", display_name="Version Admin")
        target = create_user("version-target@example.com", None, "password123", display_name="Version Target")
        headers = {"Authorization": "Bearer {}".format(create_session(admin)["token"])}
        display_session = create_session(target)["token"]
        with TestClient(app) as client:
            renamed = client.patch(
                "/api/v1/admin/users/{}".format(target["id"]), headers=headers,
                json={"display_name": "Renamed Target", "version": target["version"]},
            )
            self.assertEqual(200, renamed.status_code, renamed.text)
            self.assertEqual(200, client.get("/api/v1/auth/me", headers={"Authorization": "Bearer {}".format(display_session)}).status_code)

            stale = client.patch(
                "/api/v1/admin/users/{}/role".format(target["id"]), headers=headers,
                json={"role": "sales", "version": target["version"]},
            )
            self.assertEqual(409, stale.status_code, stale.text)
            self.assertEqual("ACCOUNT_VERSION_CONFLICT", stale.json()["error"]["code"])

            changed = client.patch(
                "/api/v1/admin/users/{}/role".format(target["id"]), headers=headers,
                json={"role": "sales", "version": renamed.json()["version"]},
            )
            self.assertEqual(200, changed.status_code, changed.text)
            self.assertEqual(401, client.get("/api/v1/auth/me", headers={"Authorization": "Bearer {}".format(display_session)}).status_code)

            page = client.get("/api/v1/admin/users?role=sales&status=enabled&page=1&page_size=1", headers=headers)
            self.assertEqual(200, page.status_code, page.text)
            self.assertEqual(1, page.json()["page_size"])
            self.assertTrue(all(item["role"] == "sales" and item["enabled"] for item in page.json()["items"]))

    def test_disabled_account_cannot_login_and_can_be_reenabled(self) -> None:
        admin = create_user("enable-admin@example.com", None, "password123", role="admin", display_name="Enable Admin")
        target = create_user("enable-target@example.com", None, "password123", display_name="Enable Target")
        headers = {"Authorization": "Bearer {}".format(create_session(admin)["token"])}
        with TestClient(app) as client:
            disabled = client.patch("/api/v1/admin/users/{}/status".format(target["id"]), headers=headers, json={"enabled": False, "version": target["version"]})
            self.assertEqual(200, disabled.status_code, disabled.text)
            self.assertIsNone(authenticate("enable-target@example.com", "password123"))
            enabled = client.patch("/api/v1/admin/users/{}/status".format(target["id"]), headers=headers, json={"enabled": True, "version": disabled.json()["version"]})
            self.assertEqual(200, enabled.status_code, enabled.text)
            self.assertIsNotNone(authenticate("enable-target@example.com", "password123"))

    def test_profile_contact_change_requires_password_and_revokes_session(self) -> None:
        user = create_user("profile-user@example.com", "+861590000092", "password123", display_name="Profile User", phone_country="CN")
        token = create_session(user)["token"]
        headers = {"Authorization": "Bearer {}".format(token)}
        with TestClient(app) as client:
            changed = client.patch("/api/v1/auth/profile/contact", headers=headers, json={"current_password": "password123", "email": "profile-new@example.com", "phone_country": "CN", "phone": "1590000092"})
            self.assertEqual(200, changed.status_code, changed.text)
            self.assertEqual("1590000092", changed.json()["phone"])
            self.assertEqual(401, client.get("/api/v1/auth/me", headers=headers).status_code)

    def test_saved_quote_can_be_downloaded_as_pdf(self) -> None:
        staff = create_user("quote-pdf@example.com", None, "password123", role="sales", display_name="Quote PDF")
        config_owner = create_user("quote-config@example.com", None, "password123", display_name="Quote Config")
        product = get_product("cr1016")
        snapshot = build_snapshot(product["id"], product["colors"][0]["code"], {})
        config = save_config(config_owner["id"], "Quote PDF configuration", product["id"], snapshot)
        headers = {"Authorization": "Bearer {}".format(create_session(staff)["token"])}
        with TestClient(app) as client:
            for currency, price in (("CNY", 1000), ("USD", 150)):
                created = client.post("/api/v1/quotes", headers=headers, json={
                    "config_id": config["id"], "title": "{} Quote PDF".format(currency), "items": [{"code": "CR1016", "name": "Test Bench", "quantity": 1, "price": price}], "total_price": price, "currency": currency,
                })
                self.assertEqual(201, created.status_code, created.text)
                response = client.get("/api/v1/quotes/{}/pdf".format(created.json()["id"]), headers=headers)
                self.assertEqual(200, response.status_code, response.text)
                self.assertEqual("application/pdf", response.headers["content-type"])
                self.assertGreater(len(response.content), 100)

    def test_cross_platform_pdf_generation(self) -> None:
        from io import BytesIO
        from pypdf import PdfReader

        product = get_product("cr1016")
        selections = {}
        for category in product["categories"]:
            if category["multiple"]:
                selections[category["id"]] = [option["id"] for option in category["options"]]
            elif category["options"]:
                selections[category["id"]] = category["options"][0]["id"]
        snapshot = build_snapshot(product["id"], product["colors"][0]["code"], selections)
        config_content = configuration_pdf(snapshot, "中文设备配置清单")
        config_reader = PdfReader(BytesIO(config_content))
        self.assertGreaterEqual(len(config_reader.pages), 1)
        self.assertIn("CR1016", config_reader.pages[0].extract_text())

        quote_content = quote_pdf({"id": "quote-test", "title": "中文报价单", "currency": "CNY", "total_price": 3200, "items": [{"code": "CR1016", "name": "共轨试验台", "quantity": 1, "price": 3200}]})
        quote_reader = PdfReader(BytesIO(quote_content))
        self.assertEqual(1, len(quote_reader.pages))
        self.assertIn("CR1016", quote_reader.pages[0].extract_text())

    def test_safe_catalog_deletion(self) -> None:
        mapped = config_option_references("cri-1016")
        self.assertGreater(mapped["mapping_count"], 0)
        self.assertFalse(delete_config_option("cri-1016"))

        category = create_config_category("临时分类", name_en="Temporary category")
        option = create_config_option(category["id"], "TEST-DELETE", "临时配置", name_en="Temporary option")
        self.assertEqual(0, config_option_references(option["id"])["mapping_count"])
        self.assertTrue(delete_config_option(option["id"]))
        self.assertEqual(0, config_category_references(category["id"])["option_count"])
        self.assertTrue(delete_config_category(category["id"]))
        self.assertFalse(delete_config_category("motor"))

    def test_alembic_upgrade_on_empty_database(self) -> None:
        with tempfile.TemporaryDirectory(prefix="boten-migration-") as folder:
            database_path = Path(folder) / "migration-test.db"
            environment = os.environ.copy()
            environment["BOTEN_DATABASE_PATH"] = str(database_path)
            process = subprocess.run(
                [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
            connection = sqlite3.connect(str(database_path))
            try:
                version_row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                columns = {row[1] for row in connection.execute("PRAGMA table_info(product_options)")}
                color_columns = {row[1] for row in connection.execute("PRAGMA table_info(product_colors)")}
                user_columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
                category_columns = {row[1] for row in connection.execute("PRAGMA table_info(categories)")}
                option_columns = {row[1] for row in connection.execute("PRAGMA table_info(options)")}
                share_item_columns = {row[1] for row in connection.execute("PRAGMA table_info(config_share_items)")}
            finally:
                connection.close()
            self.assertIsNotNone(version_row, process.stdout + process.stderr)
            self.assertEqual("20260905_0018", version_row[0])
            self.assertTrue({"products", "options", "users", "quotes", "audit_logs", "product_motor_prices", "product_specifications", "config_share_items", "product_base_option_groups", "product_base_options", "product_price_variants", "saved_catalog_items", "commerce_shares", "commerce_share_items", "commerce_quotes", "share_imports", "quote_deliveries"}.issubset(tables))
            self.assertIn("description_override_en", columns)
            self.assertTrue({"label_en", "display_color", "enabled", "version", "translation_status"}.issubset(color_columns))
            self.assertTrue({"deleted_at", "deleted_by", "delete_reason", "version", "gender", "birth_date", "signature"}.issubset(user_columns))
            self.assertTrue({"parent_id", "catalog_type", "enabled", "version", "translation_status"}.issubset(category_columns))
            self.assertTrue({"note_en", "deleted_at", "version", "translation_status"}.issubset(option_columns))
            self.assertTrue({"image_width", "image_height"}.issubset(option_columns))
            self.assertTrue({"item_type", "source_id"}.issubset(share_item_columns))


if __name__ == "__main__":
    unittest.main()
