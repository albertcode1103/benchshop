"""Add customer profile fields and share-import idempotency records."""

from alembic import op
import sqlalchemy as sa


revision = "20260905_0015"
down_revision = "20260904_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("gender", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("birth_date", sa.Text(), nullable=True))
        batch.add_column(sa.Column("signature", sa.Text(), nullable=False, server_default=""))
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS share_imports (
            id TEXT PRIMARY KEY,
            share_id TEXT NOT NULL,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            idempotency_key TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, idempotency_key)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_share_imports_user ON share_imports(user_id, created_at)")


def downgrade() -> None:
    # Profile and import records are customer data. Production rollback uses a
    # verified backup instead of destructive column or table removal.
    pass
