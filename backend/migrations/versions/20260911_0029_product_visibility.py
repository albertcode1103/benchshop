"""Per-language navigation visibility; business snapshots remain unchanged."""
from alembic import op
import sqlalchemy as sa

revision = "20260911_0029"
down_revision = "20260911_0028"
branch_labels = None
depends_on = None

def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("products")}
    for name in ("visible_zh", "visible_en"):
        if name not in columns:
            op.add_column("products", sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.true()))
    for action in ("INSERT", "UPDATE"):
        op.execute(f"CREATE TRIGGER IF NOT EXISTS product_language_{action.lower()} BEFORE {action} ON products WHEN NEW.visible_zh = 0 AND NEW.visible_en = 0 BEGIN SELECT RAISE(ABORT, 'At least one visible language required'); END")

def downgrade():
    op.execute("DROP TRIGGER product_language_insert")
    op.execute("DROP TRIGGER product_language_update")
    op.drop_column("products", "visible_en")
    op.drop_column("products", "visible_zh")
