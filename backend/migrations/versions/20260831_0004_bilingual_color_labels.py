"""Add localized color names for customer-facing catalog pages.

Revision ID: 20260831_0004
Revises: 20260831_0003
"""
from alembic import op
import sqlalchemy as sa


revision = "20260831_0004"
down_revision = "20260831_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("product_colors") as batch:
        batch.add_column(sa.Column("label_en", sa.Text(), nullable=False, server_default=""))
    op.execute("UPDATE product_colors SET label_en = label WHERE label_en = ''")
    op.execute("UPDATE product_colors SET label = '绿色', label_en = 'Green' WHERE code = 'Green' AND label = 'Green'")
    op.execute("UPDATE product_colors SET label = '红色', label_en = 'Red' WHERE code = 'Red' AND label = 'Red'")


def downgrade() -> None:
    with op.batch_alter_table("product_colors") as batch:
        batch.drop_column("label_en")
