"""Store customer addresses and preserve quotation address snapshots."""

from alembic import op

revision = "20260911_0026"
down_revision = "20260909_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    for table, column in (("users", "address"), ("commerce_quotes", "customer_address")):
        columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info({})".format(table))}
        if column not in columns:
            op.execute("ALTER TABLE {} ADD COLUMN {} TEXT NOT NULL DEFAULT ''".format(table, column))


def downgrade() -> None:
    # Retain customer information: removing columns would lose history.
    pass
