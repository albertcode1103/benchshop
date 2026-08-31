import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TEST_DIRECTORY = tempfile.TemporaryDirectory(prefix="boten-tests-")
TEST_DATABASE = Path(TEST_DIRECTORY.name) / "boten-test.db"
TEST_UPLOADS = Path(TEST_DIRECTORY.name) / "uploads"
os.environ["BOTEN_DATABASE_PATH"] = str(TEST_DATABASE)
os.environ["BOTEN_UPLOAD_DIR"] = str(TEST_UPLOADS)

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.admin_catalog_repository import (
    config_category_references,
    config_option_references,
    create_config_category,
    create_config_option,
    delete_config_category,
    delete_config_option,
    get_admin_product,
    replace_option_mappings,
    update_product_option_override,
)
from backend.audit_catalog import audit_catalog
from backend.config_repository import build_snapshot, create_share, get_share, list_saved_configs, save_config
from backend.config_routes import staff_user
from backend.database import get_connection
from backend.database_maintenance import create_backup, restore_backup, verify_database
from backend.media_routes import image_extension, store_image
from backend.main import app
from backend.pdf_service import configuration_pdf, quote_pdf
from backend.repository import get_product, list_products
from backend.seed import seed
from backend.user_repository import authenticate, create_session, create_user, get_user_by_token


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

    def test_authentication_and_session(self) -> None:
        user = create_user("workflow@example.com", None, "password123", display_name="Workflow")
        authenticated = authenticate("WORKFLOW@example.com", "password123")
        self.assertEqual(user["id"], authenticated["id"])
        session = create_session(authenticated)
        self.assertEqual(user["id"], get_user_by_token(session["token"])["id"])
        self.assertIsNone(authenticate("workflow@example.com", "wrong-password"))

    def test_phone_registration_and_login_use_international_format(self) -> None:
        with TestClient(app) as client:
            registered = client.post("/api/v1/auth/register", json={"display_name": "Phone User", "email": "phone-user@example.com", "phone": "+861590000000", "password": "password123"})
            self.assertEqual(201, registered.status_code, registered.text)
            self.assertEqual("+861590000000", registered.json()["user"]["phone"])
            logged_in = client.post("/api/v1/auth/login", json={"identifier": "+861590000000", "password": "password123"})
            self.assertEqual(200, logged_in.status_code, logged_in.text)
            invalid = client.post("/api/v1/auth/register", json={"display_name": "Invalid Phone", "email": "invalid-phone@example.com", "phone": "1590000000", "password": "password123"})
            self.assertEqual(422, invalid.status_code, invalid.text)
            incomplete = client.post("/api/v1/auth/register", json={"email": "missing-name@example.com", "phone": "+861590000001", "password": "password123"})
            self.assertEqual(422, incomplete.status_code, incomplete.text)

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
        content = b"\x89PNG\r\n\x1a\n" + b"test-image"
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
                content=b"\x89PNG\r\n\x1a\napi-test",
            )
            self.assertEqual(201, uploaded.status_code, uploaded.text)
            media_path = uploaded.json()["path"]
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
            response = client.patch("/api/v1/admin/users/{}/status".format(admin["id"]), headers=headers, json={"enabled": False})
        self.assertEqual(422, response.status_code)

    def test_saved_quote_can_be_downloaded_as_pdf(self) -> None:
        staff = create_user("quote-pdf@example.com", None, "password123", role="sales", display_name="Quote PDF")
        config_owner = create_user("quote-config@example.com", None, "password123", display_name="Quote Config")
        product = get_product("cr1016")
        snapshot = build_snapshot(product["id"], product["colors"][0]["code"], {})
        config = save_config(config_owner["id"], "Quote PDF configuration", product["id"], snapshot)
        headers = {"Authorization": "Bearer {}".format(create_session(staff)["token"])}
        with TestClient(app) as client:
            created = client.post("/api/v1/quotes", headers=headers, json={
                "config_id": config["id"], "title": "Quote PDF", "items": [{"code": "CR1016", "name": "Test Bench", "quantity": 1, "price": 1000}], "total_price": 1000, "currency": "CNY",
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
            finally:
                connection.close()
            self.assertIsNotNone(version_row, process.stdout + process.stderr)
            self.assertEqual("20260831_0004", version_row[0])
            self.assertTrue({"products", "options", "users", "quotes", "audit_logs"}.issubset(tables))
            self.assertIn("description_override_en", columns)
            self.assertIn("label_en", color_columns)


if __name__ == "__main__":
    unittest.main()
