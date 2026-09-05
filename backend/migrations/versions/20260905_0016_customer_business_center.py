"""Add customer-facing quote delivery records."""

from alembic import op


revision = "20260905_0016"
down_revision = "20260905_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_deliveries (
            id TEXT PRIMARY KEY,
            quote_id TEXT NOT NULL,
            document_version INTEGER NOT NULL DEFAULT 2 CHECK (document_version IN (1, 2)),
            recipient_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            source_share_id TEXT,
            delivered_by TEXT NOT NULL REFERENCES users(id),
            status TEXT NOT NULL DEFAULT 'delivered' CHECK (status IN ('delivered', 'withdrawn')),
            delivered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            viewed_at TEXT,
            withdrawn_at TEXT,
            UNIQUE(quote_id, recipient_user_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_quote_deliveries_recipient ON quote_deliveries(recipient_user_id, status, delivered_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_quote_deliveries_quote ON quote_deliveries(quote_id, status)")


def downgrade() -> None:
    # Delivery records are business history. Production rollback restores the
    # verified pre-migration backup instead of deleting customer data.
    pass
