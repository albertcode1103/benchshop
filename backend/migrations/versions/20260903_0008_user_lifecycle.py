"""Add account archival metadata and optimistic-lock version."""

from alembic import op


revision = "20260903_0008"
down_revision = "20260902_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {row[1] for row in op.get_bind().exec_driver_sql("PRAGMA table_info(users)")}
    if "deleted_at" not in columns:
        op.execute("ALTER TABLE users ADD COLUMN deleted_at TEXT")
    if "deleted_by" not in columns:
        op.execute("ALTER TABLE users ADD COLUMN deleted_by TEXT")
    if "delete_reason" not in columns:
        op.execute("ALTER TABLE users ADD COLUMN delete_reason TEXT NOT NULL DEFAULT ''")
    if "version" not in columns:
        op.execute("ALTER TABLE users ADD COLUMN version INTEGER NOT NULL DEFAULT 1")


def downgrade() -> None:
    # SQLite column removal requires rebuilding the users table. Preserve data.
    pass

