"""Baseline BOTEN catalog and commerce schema.

Revision ID: 20260831_0001
Revises: None
"""
from typing import Optional

from alembic import op
import sqlalchemy as sa


revision = "20260831_0001"
down_revision: Optional[str] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("title_name", sa.Text(), nullable=False),
        sa.Column("title_name_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("description_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("base_price", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("price_usd", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "product_colors",
        sa.Column("product_id", sa.Text(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("image_path", sa.Text()),
        sa.Column("is_default", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("product_id", "code"),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("description_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("multiple", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "options",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("category_id", sa.Text(), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("description_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("image_path", sa.Text()),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("price", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("price_usd", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("idx_options_category", "options", ["category_id"])
    op.create_table(
        "product_options",
        sa.Column("product_id", sa.Text(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("option_id", sa.Text(), sa.ForeignKey("options.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mapping_id", sa.Text(), nullable=False, unique=True),
        sa.Column("description_override", sa.Text()),
        sa.Column("image_override", sa.Text()),
        sa.Column("price_override", sa.Integer()),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("product_id", "option_id"),
    )
    op.create_index("idx_product_options_product", "product_options", ["product_id"])
    op.create_table(
        "users",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("email", sa.Text(), unique=True),
        sa.Column("phone", sa.Text(), unique=True),
        sa.Column("password_hash", sa.Text()),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("role IN ('guest', 'customer', 'sales', 'admin')", name="ck_users_role"),
        sa.CheckConstraint("role = 'guest' OR email IS NOT NULL OR phone IS NOT NULL", name="ck_users_contact"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_seen_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_sessions_user", "sessions", ["user_id"])
    op.create_index("idx_sessions_expiry", "sessions", ["expires_at"])
    op.create_table(
        "saved_configs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("product_id", sa.Text(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("status IN ('draft', 'shared', 'quoted', 'closed')", name="ck_saved_configs_status"),
    )
    op.create_index("idx_saved_configs_user", "saved_configs", ["user_id"])
    op.create_table(
        "config_shares",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("config_id", sa.Text(), sa.ForeignKey("saved_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("created_by", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_viewed_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_config_shares_config", "config_shares", ["config_id"])
    op.create_index("idx_config_shares_expiry", "config_shares", ["expires_at"])
    op.create_table(
        "quotes",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("config_id", sa.Text(), sa.ForeignKey("saved_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default="配置报价单"),
        sa.Column("items_json", sa.Text(), nullable=False),
        sa.Column("total_price", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.Text(), nullable=False, server_default="CNY"),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_quotes_user", "quotes", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_quotes_user", table_name="quotes")
    op.drop_table("quotes")
    op.drop_index("idx_config_shares_expiry", table_name="config_shares")
    op.drop_index("idx_config_shares_config", table_name="config_shares")
    op.drop_table("config_shares")
    op.drop_index("idx_saved_configs_user", table_name="saved_configs")
    op.drop_table("saved_configs")
    op.drop_index("idx_sessions_expiry", table_name="sessions")
    op.drop_index("idx_sessions_user", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
    op.drop_index("idx_product_options_product", table_name="product_options")
    op.drop_table("product_options")
    op.drop_index("idx_options_category", table_name="options")
    op.drop_table("options")
    op.drop_table("categories")
    op.drop_table("product_colors")
    op.drop_table("products")
