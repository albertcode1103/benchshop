"""Add immutable quotation revisions and quotation lifecycle metadata."""

from alembic import op


revision = "20260905_0017"
down_revision = "20260905_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite can add nullable/defaulted columns safely. Lifecycle validation is
    # additionally enforced by the repository to keep existing installations
    # upgradeable without rebuilding their business-record tables.
    op.execute("ALTER TABLE commerce_quotes ADD COLUMN quote_number TEXT")
    op.execute("ALTER TABLE commerce_quotes ADD COLUMN lifecycle_status TEXT NOT NULL DEFAULT 'draft'")
    op.execute("ALTER TABLE commerce_quotes ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE commerce_quotes ADD COLUMN valid_until TEXT")
    op.execute("ALTER TABLE commerce_quotes ADD COLUMN payment_terms TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE commerce_quotes ADD COLUMN delivery_terms TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE commerce_quotes ADD COLUMN tax_note TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE commerce_quotes ADD COLUMN freight_note TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE commerce_quotes ADD COLUMN sales_contact TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE commerce_quotes ADD COLUMN quote_note TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE commerce_quotes ADD COLUMN sent_at TEXT")
    op.execute("ALTER TABLE commerce_quotes ADD COLUMN archived_at TEXT")
    op.execute("ALTER TABLE commerce_quotes ADD COLUMN archived_by TEXT")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_commerce_quotes_number ON commerce_quotes(quote_number) WHERE quote_number IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_commerce_quotes_lifecycle ON commerce_quotes(lifecycle_status, updated_at)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_revisions (
            id TEXT PRIMARY KEY,
            quote_id TEXT NOT NULL REFERENCES commerce_quotes(id) ON DELETE CASCADE,
            revision_number INTEGER NOT NULL CHECK (revision_number > 0),
            snapshot_json TEXT NOT NULL,
            created_by TEXT NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(quote_id, revision_number)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_quote_revisions_quote ON quote_revisions(quote_id, revision_number DESC)")

    op.execute("ALTER TABLE quote_deliveries ADD COLUMN revision_id TEXT")
    op.execute("ALTER TABLE quote_deliveries ADD COLUMN last_viewed_revision_id TEXT")
    op.execute("ALTER TABLE quote_deliveries ADD COLUMN notification_state TEXT NOT NULL DEFAULT 'unread'")
    op.execute("CREATE INDEX IF NOT EXISTS idx_quote_deliveries_revision ON quote_deliveries(revision_id, status)")


def downgrade() -> None:
    # Revisions and delivery history are business records. Production rollback
    # is performed by restoring a verified database backup, never by dropping
    # historical data in place.
    pass
