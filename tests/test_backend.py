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
    update_product_option_override,
)
from backend.audit_catalog import audit_catalog
from backend.config_repository import build_snapshot, create_share, get_share, save_config
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

    def test_authentication_and_session(self) -> None:
        user = create_user("workflow@example.com", None, "password123", display_name="Workflow")
        authenticated = authenticate("WORKFLOW@example.com", "password123")
        self.assertEqual(user["id"], authenticated["id"])
        session = create_session(authenticated)
        self.assertEqual(user["id"], get_user_by_token(session["token"])["id"])
        self.assertIsNone(authenticate("workflow@example.com", "wrong-password"))

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

    def test_bilingual_product_option_override(self) -> None:
        product = get_product("cr1016")
        option = next(item for category in product["categories"] for item in category["options"])
        updated = update_product_option_override("cr1016", option["id"], "中文专属说明", "English product-specific note")
        self.assertIsNotNone(updated)
        english = get_product("cr1016", "en")
        translated = next(item for category in english["categories"] for item in category["options"] if item["id"] == option["id"])
        self.assertEqual("English product-specific note", translated["description"])

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
            finally:
                connection.close()
            self.assertIsNotNone(version_row, process.stdout + process.stderr)
            self.assertEqual("20260831_0003", version_row[0])
            self.assertTrue({"products", "options", "users", "quotes", "audit_logs"}.issubset(tables))
            self.assertIn("description_override_en", columns)


if __name__ == "__main__":
    unittest.main()
