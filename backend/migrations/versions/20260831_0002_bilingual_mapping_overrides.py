"""Add English product-specific option descriptions.

Revision ID: 20260831_0002
Revises: 20260831_0001
"""
from alembic import op
import sqlalchemy as sa


revision = "20260831_0002"
down_revision = "20260831_0001"
branch_labels = None
depends_on = None


def _has_column(name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return name in {column["name"] for column in inspector.get_columns("product_options")}


def upgrade() -> None:
    if not _has_column("description_override_en"):
        with op.batch_alter_table("product_options") as batch:
            batch.add_column(sa.Column("description_override_en", sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column("description_override_en"):
        with op.batch_alter_table("product_options") as batch:
            batch.drop_column("description_override_en")
