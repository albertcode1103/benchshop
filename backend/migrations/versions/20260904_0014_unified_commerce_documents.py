"""Add additive tables for mixed cart shares and quotations."""

from alembic import op


revision = "20260904_0014"
down_revision = "20260904_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS commerce_shares (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            created_by TEXT NOT NULL REFERENCES users(id),
            expires_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            title TEXT NOT NULL DEFAULT '',
            language TEXT NOT NULL DEFAULT 'zh',
            customer_name TEXT NOT NULL DEFAULT '',
            customer_email TEXT NOT NULL DEFAULT '',
            item_count INTEGER NOT NULL DEFAULT 1,
            product_summary TEXT NOT NULL DEFAULT '',
            primary_config_id TEXT REFERENCES saved_configs(id) ON DELETE SET NULL,
            view_count INTEGER NOT NULL DEFAULT 0,
            last_viewed_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS commerce_share_items (
            id TEXT PRIMARY KEY,
            share_id TEXT NOT NULL REFERENCES commerce_shares(id) ON DELETE CASCADE,
            item_type TEXT NOT NULL CHECK (item_type IN ('device_config', 'tool', 'accessory')),
            source_id TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
            display_name TEXT NOT NULL DEFAULT '',
            snapshot_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS commerce_quotes (
            id TEXT PRIMARY KEY,
            config_id TEXT REFERENCES saved_configs(id) ON DELETE SET NULL,
            source_share_id TEXT REFERENCES commerce_shares(id) ON DELETE SET NULL,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL DEFAULT '配置报价单',
            customer_name TEXT NOT NULL DEFAULT '',
            customer_email TEXT NOT NULL DEFAULT '',
            language TEXT NOT NULL DEFAULT 'zh',
            items_json TEXT NOT NULL,
            total_price REAL NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'CNY',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_commerce_shares_expiry ON commerce_shares(active, expires_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_commerce_share_items_share ON commerce_share_items(share_id, sort_order)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_commerce_quotes_user ON commerce_quotes(user_id, updated_at)")


def downgrade() -> None:
    # These tables contain immutable customer snapshots. Production rollback
    # uses a verified database backup instead of dropping business records.
    pass
