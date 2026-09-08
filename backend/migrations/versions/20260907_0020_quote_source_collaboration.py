"""Add quote source compatibility, ownership uniqueness and inquiry timing."""

from alembic import op


revision = "20260907_0020"
down_revision = "20260907_0019"
branch_labels = None
depends_on = None


def _columns(connection, table: str):
    return {row[1] for row in connection.exec_driver_sql("PRAGMA table_info({})".format(table)).fetchall()}


def upgrade() -> None:
    connection = op.get_bind()
    quote_columns = _columns(connection, "commerce_quotes")
    for name, definition in (
        ("source_type", "TEXT NOT NULL DEFAULT 'direct'"),
        ("source_document_version", "INTEGER"),
        ("source_document_id", "TEXT"),
        ("source_code", "TEXT NOT NULL DEFAULT ''"),
    ):
        if name not in quote_columns:
            op.execute("ALTER TABLE commerce_quotes ADD COLUMN {} {}".format(name, definition))
    op.execute("UPDATE commerce_quotes SET source_type = 'inquiry', source_document_id = source_inquiry_id WHERE source_inquiry_id IS NOT NULL AND (source_document_id IS NULL OR source_document_id = '')")
    op.execute("UPDATE commerce_quotes SET source_type = 'share', source_document_id = source_share_id WHERE source_share_id IS NOT NULL AND (source_document_id IS NULL OR source_document_id = '')")
    # Preserve every historical row while making the newest document the sole
    # active quote for a salesperson/source pair.
    op.execute("""
        UPDATE commerce_quotes AS older
        SET lifecycle_status = 'archived', archived_at = COALESCE(archived_at, CURRENT_TIMESTAMP)
        WHERE older.source_document_id IS NOT NULL
          AND older.lifecycle_status != 'archived'
          AND EXISTS (
              SELECT 1 FROM commerce_quotes AS newer
              WHERE newer.source_type = older.source_type
                AND newer.source_document_id = older.source_document_id
                AND newer.user_id = older.user_id
                AND newer.lifecycle_status != 'archived'
                AND (newer.updated_at > older.updated_at OR (newer.updated_at = older.updated_at AND newer.id > older.id))
          )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_commerce_quotes_source_document ON commerce_quotes(source_type, source_document_id, user_id, updated_at)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_commerce_quotes_active_source_owner ON commerce_quotes(source_type, source_document_id, user_id) WHERE source_document_id IS NOT NULL AND lifecycle_status != 'archived'")

    inquiry_columns = _columns(connection, "customer_inquiries")
    for name in ("first_quoted_at", "latest_quoted_at"):
        if name not in inquiry_columns:
            op.execute("ALTER TABLE customer_inquiries ADD COLUMN {} TEXT".format(name))
    op.execute("""
        UPDATE customer_inquiries
        SET first_quoted_at = COALESCE(first_quoted_at, quoted_at, (SELECT created_at FROM commerce_quotes WHERE id = converted_quote_id)),
            latest_quoted_at = COALESCE(latest_quoted_at, quoted_at, (SELECT updated_at FROM commerce_quotes WHERE id = converted_quote_id))
        WHERE quoted_at IS NOT NULL OR converted_quote_id IS NOT NULL
    """)


def downgrade() -> None:
    # These columns preserve commercial traceability and are intentionally kept.
    pass
