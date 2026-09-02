"""add country metadata for normalized phone login"""
from alembic import op

revision = "20260902_0007"
down_revision = "20260901_0006"
branch_labels = None
depends_on = None

def upgrade() -> None:
    columns = {row[1] for row in op.get_bind().exec_driver_sql("PRAGMA table_info(users)")}
    if "phone_country" not in columns:
        op.execute("ALTER TABLE users ADD COLUMN phone_country TEXT")
    # Existing production accounts with a Chinese E.164 number can be migrated
    # without guessing. Other countries remain editable and require confirmation.
    op.execute("UPDATE users SET phone_country='CN' WHERE phone_country IS NULL AND phone LIKE '+86%'")

def downgrade() -> None:
    # SQLite cannot safely drop a column without rebuilding the users table.
    pass
