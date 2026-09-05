"""Add explicit customer inquiry records independent from shares."""

from alembic import op


revision = "20260905_0018"
down_revision = "20260905_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_inquiries (
            id TEXT PRIMARY KEY,
            inquiry_number TEXT NOT NULL UNIQUE,
            created_by TEXT NOT NULL REFERENCES users(id),
            source_type TEXT NOT NULL CHECK (source_type IN ('current_device', 'cart')),
            status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'assigned', 'contacted', 'quoted', 'closed', 'cancelled')),
            language TEXT NOT NULL DEFAULT 'zh',
            customer_name_snapshot TEXT NOT NULL DEFAULT '',
            customer_email_snapshot TEXT NOT NULL DEFAULT '',
            customer_phone_snapshot TEXT NOT NULL DEFAULT '',
            customer_country_snapshot TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            item_count INTEGER NOT NULL DEFAULT 0 CHECK (item_count > 0),
            assigned_to TEXT REFERENCES users(id) ON DELETE SET NULL,
            converted_quote_id TEXT REFERENCES commerce_quotes(id) ON DELETE SET NULL,
            idempotency_key TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            contacted_at TEXT,
            quoted_at TEXT,
            closed_at TEXT,
            UNIQUE(created_by, idempotency_key)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_inquiry_items (
            id TEXT PRIMARY KEY,
            inquiry_id TEXT NOT NULL REFERENCES customer_inquiries(id) ON DELETE CASCADE,
            item_type TEXT NOT NULL CHECK (item_type IN ('device_config', 'tool', 'accessory')),
            source_id TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
            display_name TEXT NOT NULL DEFAULT '',
            snapshot_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_customer_inquiries_customer ON customer_inquiries(created_by, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_customer_inquiries_status ON customer_inquiries(status, assigned_to, updated_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_customer_inquiry_items_inquiry ON customer_inquiry_items(inquiry_id, sort_order)")


def downgrade() -> None:
    # Inquiry records are business history. Production rollback restores a
    # verified backup rather than dropping customer requests in place.
    pass
