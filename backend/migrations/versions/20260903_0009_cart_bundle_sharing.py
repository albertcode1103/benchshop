"""Add editable saved configurations and immutable multi-device shares."""

from alembic import op


revision = "20260903_0009"
down_revision = "20260903_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    saved_columns = {row[1] for row in bind.exec_driver_sql("PRAGMA table_info(saved_configs)")}
    if "version" not in saved_columns:
        op.execute("ALTER TABLE saved_configs ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
    if "archived_at" not in saved_columns:
        op.execute("ALTER TABLE saved_configs ADD COLUMN archived_at TEXT")

    share_columns = {row[1] for row in bind.exec_driver_sql("PRAGMA table_info(config_shares)")}
    for column, definition in (
        ("title", "TEXT NOT NULL DEFAULT ''"),
        ("language", "TEXT NOT NULL DEFAULT 'zh'"),
        ("customer_name", "TEXT NOT NULL DEFAULT ''"),
        ("customer_email", "TEXT NOT NULL DEFAULT ''"),
        ("item_count", "INTEGER NOT NULL DEFAULT 1"),
    ):
        if column not in share_columns:
            op.execute("ALTER TABLE config_shares ADD COLUMN {} {}".format(column, definition))

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS config_share_items (
            id TEXT PRIMARY KEY,
            share_id TEXT NOT NULL REFERENCES config_shares(id) ON DELETE CASCADE,
            config_id TEXT REFERENCES saved_configs(id) ON DELETE SET NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            display_name TEXT NOT NULL DEFAULT '',
            snapshot_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_config_share_items_share ON config_share_items(share_id, sort_order)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_saved_configs_active_user ON saved_configs(user_id, archived_at, updated_at)")
    op.execute(
        """
        INSERT INTO config_share_items (id, share_id, config_id, sort_order, display_name, snapshot_json)
        SELECT lower(hex(randomblob(16))), s.id, s.config_id, 0, c.name, c.snapshot_json
        FROM config_shares s
        JOIN saved_configs c ON c.id = s.config_id
        WHERE NOT EXISTS (SELECT 1 FROM config_share_items i WHERE i.share_id = s.id)
        """
    )
    op.execute(
        """
        UPDATE config_shares
        SET customer_name = COALESCE((SELECT display_name FROM users WHERE id = created_by), ''),
            customer_email = COALESCE((SELECT email FROM users WHERE id = created_by), ''),
            item_count = (SELECT COUNT(*) FROM config_share_items WHERE share_id = config_shares.id)
        """
    )


def downgrade() -> None:
    # Preserve new share snapshots and archive metadata on SQLite downgrades.
    pass
