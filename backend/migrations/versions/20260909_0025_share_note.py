"""Add a short note to configuration shares."""

from alembic import op


revision = "20260909_0025"
down_revision = "20260908_0024"
branch_labels = None
depends_on = None


def _columns(table: str):
    return {row[1] for row in op.get_bind().exec_driver_sql(f"PRAGMA table_info({table})").fetchall()}


def upgrade() -> None:
    for table in ("config_shares", "commerce_shares"):
        if "note" not in _columns(table):
            op.execute(f"ALTER TABLE {table} ADD COLUMN note TEXT NOT NULL DEFAULT ''")


def downgrade() -> None:
    # Retain the harmless column instead of rebuilding live SQLite tables.
    return
