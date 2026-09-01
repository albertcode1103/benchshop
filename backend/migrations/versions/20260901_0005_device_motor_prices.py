"""Add per-device motor prices."""
from alembic import op
import sqlalchemy as sa

revision = "20260901_0005"
down_revision = "20260831_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_motor_prices",
        sa.Column("product_id", sa.Text(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("motor_option_id", sa.Text(), sa.ForeignKey("options.id", ondelete="CASCADE"), nullable=False),
        sa.Column("base_price_cny", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("base_price_usd", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("product_id", "motor_option_id"),
    )
    op.create_index("idx_product_motor_prices_product", "product_motor_prices", ["product_id"])
    op.execute("""
        INSERT INTO product_motor_prices (product_id, motor_option_id, base_price_cny, base_price_usd)
        SELECT po.product_id, po.option_id, p.base_price, p.price_usd
        FROM product_options po
        JOIN options o ON o.id = po.option_id AND o.category_id = 'motor'
        JOIN products p ON p.id = po.product_id
        WHERE po.enabled = 1
    """)


def downgrade() -> None:
    op.drop_index("idx_product_motor_prices_product", table_name="product_motor_prices")
    op.drop_table("product_motor_prices")
