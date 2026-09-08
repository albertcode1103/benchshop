"""Track share provenance through imported carts and customer inquiries."""

from alembic import op


revision = "20260908_0021"
down_revision = "20260907_0020"
branch_labels = None
depends_on = None


def _columns(connection, table: str):
    return {row[1] for row in connection.exec_driver_sql("PRAGMA table_info({})".format(table)).fetchall()}


def upgrade() -> None:
    connection = op.get_bind()
    if "source_trace_json" not in _columns(connection, "saved_configs"):
        op.execute("ALTER TABLE saved_configs ADD COLUMN source_trace_json TEXT NOT NULL DEFAULT '[]'")
    if "source_trace_json" not in _columns(connection, "saved_catalog_items"):
        op.execute("ALTER TABLE saved_catalog_items ADD COLUMN source_trace_json TEXT NOT NULL DEFAULT '[]'")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_inquiry_sources (
            id TEXT PRIMARY KEY,
            inquiry_id TEXT NOT NULL REFERENCES customer_inquiries(id) ON DELETE CASCADE,
            source_key TEXT NOT NULL,
            source_share_id TEXT,
            source_share_code TEXT NOT NULL DEFAULT '',
            source_document_version INTEGER NOT NULL DEFAULT 1,
            item_count INTEGER NOT NULL DEFAULT 0 CHECK (item_count >= 0),
            quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(inquiry_id, source_key)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_customer_inquiry_sources_inquiry ON customer_inquiry_sources(inquiry_id, created_at, id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_customer_inquiry_sources_share ON customer_inquiry_sources(source_share_id, source_share_code)")


def downgrade() -> None:
    # Provenance is business history and remains intentionally additive.
    pass
