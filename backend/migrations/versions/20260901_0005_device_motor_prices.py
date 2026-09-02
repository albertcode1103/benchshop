"""Add per-device motor prices."""
from alembic import op

revision = "20260901_0005"
down_revision = "20260831_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Earlier installations created this table in initialize_database() before
    # Alembic tracked the migration. Keep the upgrade safe for those databases.
    op.execute("""
        CREATE TABLE IF NOT EXISTS product_motor_prices (
            product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            motor_option_id TEXT NOT NULL REFERENCES options(id) ON DELETE CASCADE,
            base_price_cny INTEGER NOT NULL DEFAULT 0,
            base_price_usd INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (product_id, motor_option_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_product_motor_prices_product ON product_motor_prices(product_id)")
    op.execute("""
        INSERT OR IGNORE INTO product_motor_prices (product_id, motor_option_id, base_price_cny, base_price_usd)
        SELECT po.product_id, po.option_id, p.base_price, p.price_usd
        FROM product_options po
        JOIN options o ON o.id = po.option_id AND o.category_id = 'motor'
        JOIN products p ON p.id = po.product_id
        WHERE po.enabled = 1
    """)


def downgrade() -> None:
    op.drop_index("idx_product_motor_prices_product", table_name="product_motor_prices")
    op.drop_table("product_motor_prices")
