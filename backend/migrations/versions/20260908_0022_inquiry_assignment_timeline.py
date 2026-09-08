"""Record the first inquiry assignment for the customer-service timeline."""

from alembic import op


revision = "20260908_0022"
down_revision = "20260908_0021"
branch_labels = None
depends_on = None


def _columns(connection, table: str):
    return {row[1] for row in connection.exec_driver_sql("PRAGMA table_info({})".format(table)).fetchall()}


def upgrade() -> None:
    connection = op.get_bind()
    if "assigned_at" not in _columns(connection, "customer_inquiries"):
        op.execute("ALTER TABLE customer_inquiries ADD COLUMN assigned_at TEXT")
    op.execute(
        """
        UPDATE customer_inquiries
        SET assigned_at = COALESCE(assigned_at, created_at)
        WHERE assigned_to IS NOT NULL
        """
    )


def downgrade() -> None:
    # Assignment time is part of the business audit trail and remains additive.
    pass
