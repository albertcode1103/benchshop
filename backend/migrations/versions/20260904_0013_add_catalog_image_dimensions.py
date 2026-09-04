"""Add missing image dimensions to upgraded catalog option tables."""

from alembic import op


revision = "20260904_0013"
down_revision = "20260904_0012"
branch_labels = None
depends_on = None


def _columns(bind, table: str):
    return {row[1] for row in bind.exec_driver_sql("PRAGMA table_info({})".format(table))}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _columns(bind, "options")
    if "image_width" not in columns:
        op.execute("ALTER TABLE options ADD COLUMN image_width INTEGER")
    if "image_height" not in columns:
        op.execute("ALTER TABLE options ADD COLUMN image_height INTEGER")


def downgrade() -> None:
    # Keep additive media metadata. Production rollback uses the verified
    # pre-migration database snapshot rather than destructive column removal.
    pass
