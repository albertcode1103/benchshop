"""Personal record visibility and owner-controlled share lifecycle."""
from alembic import op

revision = "20260911_0027"
down_revision = "20260911_0026"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE IF NOT EXISTS personal_business_visibility (
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        resource_type TEXT NOT NULL CHECK(resource_type IN ('shares','inquiries','quotes')),
        resource_id TEXT NOT NULL,
        hidden INTEGER NOT NULL DEFAULT 0 CHECK(hidden IN (0,1)),
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, resource_type, resource_id)
    )""")
    connection = op.get_bind()
    for table in ("commerce_shares", "config_shares"):
        columns = {row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table})")}
        if "owner_closed" not in columns:
            op.execute(f"ALTER TABLE {table} ADD COLUMN owner_closed INTEGER NOT NULL DEFAULT 0")
        if "customer_version" not in columns:
            op.execute(f"ALTER TABLE {table} ADD COLUMN customer_version INTEGER NOT NULL DEFAULT 1")


def downgrade():
    # Retain personal choices and business history.
    pass
