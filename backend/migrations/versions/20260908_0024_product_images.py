"""Add ordered product gallery images."""

from alembic import op


revision = "20260908_0024"
down_revision = "20260908_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS product_images (
            id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            image_path TEXT NOT NULL,
            image_width INTEGER,
            image_height INTEGER,
            alt_zh TEXT NOT NULL DEFAULT '',
            alt_en TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_product_images_product ON product_images(product_id, sort_order)")


def downgrade() -> None:
    # Gallery records are retained to avoid destructive loss of media metadata.
    pass
