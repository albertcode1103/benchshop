import os
import sqlite3
import tempfile
import unittest
from pathlib import Path


TEST_DIRECTORY = tempfile.TemporaryDirectory(prefix="boten-tests-")
TEST_DATABASE = Path(TEST_DIRECTORY.name) / "boten-test.db"
os.environ["BOTEN_DATABASE_PATH"] = str(TEST_DATABASE)

from fastapi import HTTPException

from backend.admin_catalog_repository import update_product_option_override
from backend.audit_catalog import audit_catalog
from backend.config_repository import build_snapshot, create_share, get_share, save_config
from backend.config_routes import staff_user
from backend.database import get_connection
from backend.database_maintenance import create_backup, restore_backup, verify_database
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


if __name__ == "__main__":
    unittest.main()
