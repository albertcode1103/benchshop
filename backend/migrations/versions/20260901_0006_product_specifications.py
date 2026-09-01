"""add editable product specifications"""

from alembic import op

revision = "20260901_0006"
down_revision = "20260901_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS product_specifications (
            id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            label TEXT NOT NULL DEFAULT '',
            label_en TEXT NOT NULL DEFAULT '',
            value TEXT NOT NULL DEFAULT '',
            value_en TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_product_specifications_product ON product_specifications(product_id, sort_order)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS product_specifications")
