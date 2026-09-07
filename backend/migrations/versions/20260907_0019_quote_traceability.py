"""Add inquiry traceability and idempotent quote delivery."""

from alembic import op


revision = "20260907_0019"
down_revision = "20260905_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE commerce_quotes ADD COLUMN source_inquiry_id TEXT")
    op.execute("CREATE INDEX IF NOT EXISTS idx_commerce_quotes_source_inquiry ON commerce_quotes(source_inquiry_id)")
    op.execute("ALTER TABLE quote_deliveries ADD COLUMN idempotency_key TEXT")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_quote_deliveries_idempotency "
        "ON quote_deliveries(delivered_by, idempotency_key) WHERE idempotency_key IS NOT NULL"
    )


def downgrade() -> None:
    # Business history columns are retained on rollback; restoring the verified
    # pre-migration backup is safer than rebuilding SQLite tables destructively.
    pass
