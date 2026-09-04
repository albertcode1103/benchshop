"""Normalize catalog labels and collapse non-optional child categories.

Revision ID: 20260904_0012
Revises: 20260903_0011
"""

from alembic import op


revision = "20260904_0012"
down_revision = "20260903_0011"
branch_labels = None
depends_on = None


OPTIONAL_LABELS = (
    ("cri", "共轨喷油器测试套件", "Common Rail Injector Test Kits", 1),
    ("heui", "HEUI 中压胎具", "HEUI Medium-Pressure Fixtures", 2),
    ("eui-eup", "单体泵泵喷嘴胎具", "Unit Pump / Unit Injector Fixtures", 3),
    ("crp", "共轨泵工装", "Common Rail Pump Fixtures", 4),
    ("extension", "凸轮箱扩展功能", "Cam Box Extensions", 5),
    ("ec9137acb480", "BT618机械试验台拓展功能", "BT618 Mechanical Test Bench Extensions", 0),
)


def upgrade() -> None:
    bind = op.get_bind()
    for category_id, name_zh, name_en, sort_order in OPTIONAL_LABELS:
        bind.exec_driver_sql(
            """
            UPDATE categories
            SET name = ?, name_en = ?, sort_order = ?,
                translation_status = 'reviewed', version = version + 1
            WHERE id = ? AND parent_id = 'catalog-optional'
            """,
            (name_zh, name_en, sort_order, category_id),
        )

    # Tools and accessories are direct purchasable catalogs. Existing item IDs
    # stay unchanged; only redundant presentation-only category shells go away.
    for root_id in ("catalog-tools", "catalog-accessories"):
        children = bind.exec_driver_sql(
            "SELECT id FROM categories WHERE parent_id = ? ORDER BY sort_order, id",
            (root_id,),
        ).fetchall()
        for child in children:
            child_id = child[0]
            bind.exec_driver_sql(
                "UPDATE options SET category_id = ? WHERE category_id = ?",
                (root_id, child_id),
            )
            bind.exec_driver_sql("DELETE FROM categories WHERE id = ?", (child_id,))


def downgrade() -> None:
    # This migration only normalizes labels and removes empty hierarchy shells.
    # Restoring an older deployment should use the verified database backup so
    # no later catalog edits are discarded.
    pass
