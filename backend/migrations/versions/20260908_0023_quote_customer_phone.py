"""Persist manually entered quotation customer phone numbers."""

from alembic import op


revision = "20260908_0023"
down_revision = "20260908_0022"
branch_labels = None
depends_on = None


def _columns(connection, table: str):
    return {row[1] for row in connection.exec_driver_sql("PRAGMA table_info({})".format(table)).fetchall()}


def upgrade() -> None:
    connection = op.get_bind()
    if "customer_phone" not in _columns(connection, "commerce_quotes"):
        op.execute("ALTER TABLE commerce_quotes ADD COLUMN customer_phone TEXT NOT NULL DEFAULT ''")


def downgrade() -> None:
    # Customer contact data is additive and retained for historical quotations.
    pass
