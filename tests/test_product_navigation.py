import os
from pathlib import Path
import subprocess
import sys

def test_navigation_migration_and_order(tmp_path):
    script = '''
from backend.database_upgrade import upgrade_database
from backend.database import get_connection
from backend.admin_catalog_repository import create_product, list_admin_products
from backend.repository import list_products
from backend.admin_routes import reorder_products, ProductOrderRequest
from fastapi import HTTPException
upgrade_database()
with get_connection() as db:
    db.execute("INSERT INTO users(id,email,role) VALUES('test','test@example.test','admin')")
for ident in ("one", "two"):
    create_product({"id":ident,"name":ident})
with get_connection() as db:
    assert all(row[0] and row[1] for row in db.execute("SELECT visible_zh,visible_en FROM products"))
    db.execute("UPDATE products SET visible_zh=0 WHERE id='two'")
items = list_admin_products()
assert len(list_products("zh")) == len(items)  # Full data remains available; navigation filters metadata.
request = ProductOrderRequest(items=[{"id":item["id"],"version":item["version"]} for item in reversed(items)])
result = reorder_products(request, {"id":"test", "role":"admin"})
assert [i["id"] for i in result["items"]] == [i["id"] for i in reversed(items)]
try:
    reorder_products(request, {"id":"test", "role":"admin"})
    raise AssertionError("Stale order accepted")
except HTTPException as error:
    assert error.status_code == 409
with get_connection() as db:
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not db.execute("PRAGMA foreign_key_check").fetchall()
'''
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", script], cwd=Path(__file__).resolve().parents[1], env=dict(os.environ, BOTEN_DATABASE_PATH=str(tmp_path / "navigation.db")), capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
