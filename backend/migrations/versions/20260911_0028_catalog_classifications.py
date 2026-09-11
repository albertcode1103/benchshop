"""Add approved tool/accessory classifications without rewriting business snapshots."""
from alembic import op

revision = "20260911_0028"
down_revision = "20260911_0027"
branch_labels = None
depends_on = None

CATEGORIES = (
    ("tools-repair", "维修工具", "Repair Tools", "tools"),
    ("tools-measuring", "测量工具", "Measuring Tools", "tools"),
    ("tools-disassembly", "拆装工具", "Disassembly and Assembly Tools", "tools"),
    ("tools-other", "其他工具", "Other Tools", "tools"),
    ("accessories-cables", "测试线", "Test Cables", "accessories"),
    ("accessories-hoses", "油管", "Hoses", "accessories"),
    ("accessories-adapters", "适配器", "Adapters", "accessories"),
    ("accessories-plugs", "插头", "Plugs", "accessories"),
    ("accessories-connectors", "接头", "Connectors", "accessories"),
    ("accessories-other", "其他", "Other", "accessories"),
)
REPAIR = {"BT-WB", "BTC-C7C9", "BTC-C1213", "BTC-E1E3", "BTC-BSV", "BTC-HPI", "BTC-M11N14", "BTC-M11", "BTC-BUIP"}
MEASURING = {"BT-B024", "BT-S200", "BT-S60H", *(f"TEST-TOOL-{i:02d}" for i in (1, 2, 3, 4, 5, 7, 8, 9, 10))}
DISASSEMBLY = {"BTC-0003", "BTC-0004", "BTC-0005", "BTC-DS22", "BTC-DS40", "TEST-TOOL-06"}


def upgrade():
    db = op.get_bind()
    for index, (identifier, zh, en, kind) in enumerate(CATEGORIES):
        existing = db.exec_driver_sql("SELECT parent_id,catalog_type FROM categories WHERE id=?", (identifier,)).fetchone()
        if existing is not None and tuple(existing) != ("catalog-" + kind, kind):
            raise RuntimeError("Classification ID conflicts with an existing category: " + identifier)
        db.exec_driver_sql("""INSERT OR IGNORE INTO categories
            (id,name,name_en,description,description_en,multiple,sort_order,parent_id,catalog_type,enabled,version,translation_status)
            VALUES (?,?,?,'','',1,?,?,?,1,1,'reviewed')""", (identifier, zh, en, index if kind == "tools" else index - 4, "catalog-" + kind, kind))
    # Only unclassified, non-deleted records move. Existing child classifications
    # and all saved cart/share/inquiry/quotation JSON remain untouched.
    rows = db.exec_driver_sql("SELECT id,code,category_id FROM options WHERE deleted_at IS NULL AND category_id IN ('catalog-tools','catalog-accessories')").fetchall()
    for identifier, code, category in rows:
        code = str(code or "").upper().strip()
        target = "accessories-other"
        if category == "catalog-tools":
            target = "tools-repair" if code in REPAIR else "tools-measuring" if code in MEASURING else "tools-disassembly" if code in DISASSEMBLY else "tools-other"
        db.exec_driver_sql("UPDATE options SET category_id=?,version=version+1 WHERE id=?", (target, identifier))


def downgrade():
    # Restoring requires the verified pre-migration backup, not destructive relabeling.
    pass
