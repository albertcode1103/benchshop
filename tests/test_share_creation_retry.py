import os
from pathlib import Path
import subprocess
import sys

def test_share_retry_concurrent_and_quota(tmp_path):
    script = '''
from concurrent.futures import ThreadPoolExecutor
from backend.database_upgrade import upgrade_database
from backend.database import get_connection
from backend import commerce_repository as repo
upgrade_database()
with get_connection() as db:
    db.execute("INSERT INTO users(id,email,role) VALUES('qa','qa@example.test','customer')")
repo._load_share_item = lambda *args: {"item_type":"tool","source_id":"fixture","quantity":1,"display_name":"Fixture","payload":{"name":"Fixture"},"product_model":""}
repo._canonical_cart_order = lambda item: 0
refs = [{"item_type":"tool","id":"fixture"}]
def create(_): return repo.create_commerce_share(refs,"qa","en","Note","same-request-123")
with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(create, range(4)))
assert len({item["code"] for item in results}) == 1
with get_connection() as db:
    assert db.execute("SELECT COUNT(*) FROM commerce_shares").fetchone()[0] == 1
for number in range(9): repo.create_commerce_share(refs,"qa","en","Note",f"another-request-{number}")
assert create(0)["code"] == results[0]["code"]
try:
    repo.create_commerce_share(refs,"qa","en","Changed","same-request-123")
    raise AssertionError("Changed retry payload accepted")
except repo.CatalogValidationError:
    pass
with get_connection() as db:
    assert db.execute("SELECT COUNT(*) FROM commerce_shares").fetchone()[0] == 10
'''
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", script], cwd=Path(__file__).resolve().parents[1], env=dict(os.environ, BOTEN_DATABASE_PATH=str(tmp_path / "retry.db")), capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
