"""Classification upgrade and validation run in a separate, disposable database."""
import os
from pathlib import Path
import subprocess
import sys


def test_classifications_preserve_history_and_require_leaf(tmp_path):
    env = dict(os.environ, BOTEN_DATABASE_PATH=str(tmp_path / "catalog.db"))
    script = r'''
from alembic import command
from alembic.config import Config
from backend.database import get_connection
from backend.database_upgrade import upgrade_database
command.upgrade(Config("alembic.ini"), "20260911_0027")
with get_connection() as db:
    for ident, code, category, deleted in [
        ("repair", "BT-WB", "catalog-tools", None),
        ("measure", "BT-S200", "catalog-tools", None),
        ("disassemble", "BTC-DS22", "catalog-tools", None),
        ("unknown", "UNKNOWN-01", "catalog-tools", None),
        ("acc", "ACC-01", "catalog-accessories", None),
        ("deleted", "DELETED-01", "catalog-accessories", "2026-09-01"),
    ]:
        db.execute("INSERT INTO options(id,category_id,code,name,name_en,price,price_usd,image_path,sort_order,deleted_at) VALUES(?,?,?,'名称','Name',123,45,'/images/example.png',17,?)", (ident,category,code,deleted))
    db.execute("CREATE TABLE history_sentinel (snapshot TEXT)")
    db.execute("INSERT INTO history_sentinel VALUES (?)", ('{"category_id":"catalog-tools","price":123}',))
    columns = [row[1] for row in db.execute("PRAGMA table_info(options)") if row[1] not in ("category_id", "version")]
    before = [tuple(row) for row in db.execute("SELECT " + ','.join(columns) + " FROM options ORDER BY id")]
upgrade_database()
upgrade_database()
with get_connection() as db:
    after = [tuple(row) for row in db.execute("SELECT " + ','.join(columns) + " FROM options ORDER BY id")]
    assert before == after
    assert db.execute("SELECT snapshot FROM history_sentinel").fetchone()[0] == '{"category_id":"catalog-tools","price":123}'
    assigned = dict(db.execute("SELECT id,category_id FROM options"))
    assert assigned == {"repair":"tools-repair", "measure":"tools-measuring", "disassemble":"tools-disassembly", "unknown":"tools-other", "acc":"accessories-other", "deleted":"catalog-accessories"}
    assert not db.execute("PRAGMA foreign_key_check").fetchall()
from backend.catalog_cart_repository import list_public_catalog_categories
from backend.catalog_refactor_repository import create_catalog_item, update_catalog_item, CatalogValidationError
from backend.admin_catalog_repository import create_config_option, delete_config_category, update_config_category
tools = list_public_catalog_categories("tools", "zh")
assert [row["name"] for row in tools] == ["维修工具", "测量工具", "拆装工具", "其他工具"]
accessories = list_public_catalog_categories("accessories", "en")
assert len(accessories) == 6 and accessories[0]["name"] == "Test Cables"
for invalid in ("", "catalog-tools", "catalog-accessories", "missing"):
    for create in (lambda: create_catalog_item(category_id=invalid,code="NEW-01",name_zh="新工具",name_en="New tool"), lambda: create_config_option(invalid,"NEW-01","新工具")):
        try:
            create()
            raise AssertionError("Invalid category accepted: " + invalid)
        except CatalogValidationError:
            pass
item = create_catalog_item(category_id="tools-measuring",code="NEW-01",name_zh="新工具",name_en="New tool")
assert item["category_id"] == "tools-measuring"
for forbidden in ("accessories-other",):
    try:
        update_catalog_item(item["id"],version=item["version"],category_id=forbidden,code="NEW-01",name_zh="新工具",name_en="New tool")
        raise AssertionError("Unreferenced item moved across directories")
    except CatalogValidationError as error:
        assert error.code == "CATALOG_ITEM_TYPE_CHANGE_FORBIDDEN"
with get_connection() as db:
    unchanged = db.execute("SELECT category_id,version FROM options WHERE id=?",(item["id"],)).fetchone()
    assert tuple(unchanged) == ("tools-measuring",item["version"])
item = update_catalog_item(item["id"],version=item["version"],category_id="tools-repair",code="NEW-01",name_zh="新工具",name_en="New tool")
assert item["category_id"] == "tools-repair"
try:
    update_catalog_item(item["id"],version=item["version"],category_id="catalog-tools",code="NEW-01",name_zh="新工具",name_en="New tool")
    raise AssertionError("Root accepted during edit")
except CatalogValidationError:
    pass
assert delete_config_category("accessories-hoses") is False
try:
    update_config_category("accessories-hoses", {"version":1,"name":"Changed"})
    raise AssertionError("Fixed classification renamed via legacy API")
except CatalogValidationError:
    pass
from backend.catalog_refactor_repository import create_catalog_category, update_catalog_category_v2, delete_catalog_category_v2
for root, kind in (("catalog-tools", "tools"), ("catalog-accessories", "accessories")):
    category = create_catalog_category(parent_id=root, name_zh="新增类别", name_en="New category")
    assert category["catalog_type"] == kind
    assert any(c["id"] == category["id"] for c in list_public_catalog_categories(kind, "en"))
    try:
        create_catalog_category(parent_id=category["id"], name_zh="嵌套", name_en="Nested")
        raise AssertionError("Nested category accepted")
    except CatalogValidationError:
        pass
    try:
        create_catalog_category(parent_id=root, name_zh="新增类别", name_en="Duplicate")
        raise AssertionError("Duplicate accepted")
    except CatalogValidationError:
        pass
    edited = update_catalog_category_v2(category["id"], version=category["version"], name_zh="修改类别", name_en="Edited category", sort_order=19)
    assert edited["sort_order"] == 19
    created_item = create_catalog_item(category_id=category["id"], code="NEW-" + kind.upper(), name_zh="新项目", name_en="New item")
    try:
        delete_catalog_category_v2(category["id"])
        raise AssertionError("Nonempty category deleted")
    except CatalogValidationError as error:
        assert error.code == "CATALOG_CATEGORY_NOT_EMPTY"
    update_catalog_category_v2(category["id"], version=edited["version"], name_zh="修改类别", name_en="Edited category", enabled=False)
    assert not any(c["id"] == category["id"] for c in list_public_catalog_categories(kind, "en"))
print("classification migration, history preservation, public categories and validation passed")
'''
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", script],
                            cwd=Path(__file__).resolve().parents[1], env=env,
                            capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
