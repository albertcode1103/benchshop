"""Add the catalog refactor foundation without removing legacy data."""

from alembic import op


revision = "20260903_0010"
down_revision = "20260903_0009"
branch_labels = None
depends_on = None


def _columns(bind, table: str):
    return {row[1] for row in bind.exec_driver_sql("PRAGMA table_info({})".format(table))}


def _add_column(bind, table: str, name: str, definition: str) -> None:
    if name not in _columns(bind, table):
        op.execute("ALTER TABLE {} ADD COLUMN {} {}".format(table, name, definition))


def upgrade() -> None:
    bind = op.get_bind()

    for name, definition in (
        ("version", "INTEGER NOT NULL DEFAULT 1"),
        ("translation_status", "TEXT NOT NULL DEFAULT 'reviewed'"),
    ):
        _add_column(bind, "products", name, definition)

    for name, definition in (
        ("parent_id", "TEXT"),
        ("catalog_type", "TEXT NOT NULL DEFAULT 'optional'"),
        ("enabled", "INTEGER NOT NULL DEFAULT 1"),
        ("version", "INTEGER NOT NULL DEFAULT 1"),
        ("translation_status", "TEXT NOT NULL DEFAULT 'reviewed'"),
    ):
        _add_column(bind, "categories", name, definition)

    for name, definition in (
        ("note_en", "TEXT NOT NULL DEFAULT ''"),
        ("version", "INTEGER NOT NULL DEFAULT 1"),
        ("deleted_at", "TEXT"),
        ("translation_status", "TEXT NOT NULL DEFAULT 'reviewed'"),
    ):
        _add_column(bind, "options", name, definition)

    for name, definition in (
        ("display_color", "TEXT NOT NULL DEFAULT '#374151'"),
        ("image_width", "INTEGER"),
        ("image_height", "INTEGER"),
        ("enabled", "INTEGER NOT NULL DEFAULT 1"),
        ("version", "INTEGER NOT NULL DEFAULT 1"),
        ("translation_status", "TEXT NOT NULL DEFAULT 'reviewed'"),
    ):
        _add_column(bind, "product_colors", name, definition)

    op.execute(
        """
        UPDATE categories
        SET catalog_type = CASE
            WHEN id IN ('motor', 'voltage') THEN 'legacy_basic'
            WHEN lower(trim(name_en)) IN ('bench accessory', 'accessory', 'accessories') THEN 'accessories'
            ELSE 'optional'
        END
        """
    )
    op.execute(
        """
        UPDATE options
        SET translation_status = CASE
            WHEN trim(COALESCE(name_en, '')) = ''
              OR (trim(COALESCE(description, '')) <> '' AND trim(COALESCE(description_en, '')) = '')
            THEN 'missing'
            ELSE 'reviewed'
        END
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS product_base_option_groups (
            id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            option_type TEXT NOT NULL CHECK (option_type IN ('motor', 'power', 'channel')),
            required INTEGER NOT NULL DEFAULT 1 CHECK (required IN (0, 1)),
            single_select INTEGER NOT NULL DEFAULT 1 CHECK (single_select = 1),
            sort_order INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(product_id, option_type)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS product_base_options (
            id TEXT PRIMARY KEY,
            group_id TEXT NOT NULL REFERENCES product_base_option_groups(id) ON DELETE CASCADE,
            name_zh TEXT NOT NULL,
            name_en TEXT NOT NULL DEFAULT '',
            price_cny_minor INTEGER NOT NULL DEFAULT 0 CHECK (price_cny_minor >= 0),
            price_usd_minor INTEGER NOT NULL DEFAULT 0 CHECK (price_usd_minor >= 0),
            price_confirmed INTEGER NOT NULL DEFAULT 0 CHECK (price_confirmed IN (0, 1)),
            is_free INTEGER NOT NULL DEFAULT 0 CHECK (is_free IN (0, 1)),
            sort_order INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
            version INTEGER NOT NULL DEFAULT 1,
            translation_status TEXT NOT NULL DEFAULT 'machine_draft',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (is_free = 0 OR (price_cny_minor = 0 AND price_usd_minor = 0))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS product_price_variants (
            id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            motor_option_id TEXT REFERENCES product_base_options(id) ON DELETE RESTRICT,
            channel_option_id TEXT REFERENCES product_base_options(id) ON DELETE RESTRICT,
            price_cny_minor INTEGER NOT NULL DEFAULT 0 CHECK (price_cny_minor >= 0),
            price_usd_minor INTEGER NOT NULL DEFAULT 0 CHECK (price_usd_minor >= 0),
            price_confirmed INTEGER NOT NULL DEFAULT 0 CHECK (price_confirmed IN (0, 1)),
            enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (motor_option_id IS NOT NULL OR channel_option_id IS NOT NULL)
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_product_price_variants_combo
        ON product_price_variants (
            product_id,
            COALESCE(motor_option_id, ''),
            COALESCE(channel_option_id, '')
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS saved_catalog_items (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            option_id TEXT REFERENCES options(id) ON DELETE SET NULL,
            catalog_type TEXT NOT NULL CHECK (catalog_type IN ('tools', 'accessories')),
            quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
            snapshot_json TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            archived_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    for name, definition in (
        ("item_type", "TEXT NOT NULL DEFAULT 'device_config'"),
        ("source_id", "TEXT"),
    ):
        _add_column(bind, "config_share_items", name, definition)

    op.execute("CREATE INDEX IF NOT EXISTS idx_base_option_groups_product ON product_base_option_groups(product_id, option_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_base_options_group ON product_base_options(group_id, sort_order)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_price_variants_product ON product_price_variants(product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_saved_catalog_items_user ON saved_catalog_items(user_id, archived_at, updated_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id, sort_order)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_categories_type ON categories(catalog_type, enabled, sort_order)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_options_active_category ON options(category_id, enabled, deleted_at, sort_order)")


def downgrade() -> None:
    # Additive SQLite migrations are intentionally preserved. Production
    # rollback uses the verified pre-migration database snapshot so newly
    # entered catalog data is never silently deleted by an Alembic downgrade.
    pass
