import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import DATABASE_PATH


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_en TEXT NOT NULL DEFAULT '',
    title_name TEXT NOT NULL,
    title_name_en TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    description_en TEXT NOT NULL DEFAULT '',
    base_price INTEGER NOT NULL DEFAULT 0,
    price_usd INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    translation_status TEXT NOT NULL DEFAULT 'reviewed',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_colors (
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    label TEXT NOT NULL,
    label_en TEXT NOT NULL DEFAULT '',
    image_path TEXT,
    display_color TEXT NOT NULL DEFAULT '#374151',
    image_width INTEGER,
    image_height INTEGER,
    is_default INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    version INTEGER NOT NULL DEFAULT 1,
    translation_status TEXT NOT NULL DEFAULT 'reviewed',
    PRIMARY KEY (product_id, code)
);

CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_en TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    description_en TEXT NOT NULL DEFAULT '',
    multiple INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    parent_id TEXT,
    catalog_type TEXT NOT NULL DEFAULT 'optional',
    enabled INTEGER NOT NULL DEFAULT 1,
    version INTEGER NOT NULL DEFAULT 1,
    translation_status TEXT NOT NULL DEFAULT 'reviewed'
);

CREATE TABLE IF NOT EXISTS options (
    id TEXT PRIMARY KEY,
    category_id TEXT NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    name_en TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    description_en TEXT NOT NULL DEFAULT '',
    image_path TEXT,
    image_width INTEGER,
    image_height INTEGER,
    notes TEXT NOT NULL DEFAULT '',
    note_en TEXT NOT NULL DEFAULT '',
    price INTEGER NOT NULL DEFAULT 0,
    price_usd INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    deleted_at TEXT,
    translation_status TEXT NOT NULL DEFAULT 'reviewed'
);

CREATE TABLE IF NOT EXISTS product_options (
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    option_id TEXT NOT NULL REFERENCES options(id) ON DELETE CASCADE,
    mapping_id TEXT NOT NULL UNIQUE,
    description_override TEXT,
    description_override_en TEXT,
    image_override TEXT,
    price_override INTEGER,
    enabled INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (product_id, option_id)
);

CREATE INDEX IF NOT EXISTS idx_options_category ON options(category_id);
CREATE INDEX IF NOT EXISTS idx_product_options_product ON product_options(product_id);

CREATE TABLE IF NOT EXISTS product_motor_prices (
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    motor_option_id TEXT NOT NULL REFERENCES options(id) ON DELETE CASCADE,
    base_price_cny INTEGER NOT NULL DEFAULT 0,
    base_price_usd INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id, motor_option_id)
);

CREATE INDEX IF NOT EXISTS idx_product_motor_prices_product ON product_motor_prices(product_id);

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
);

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
);

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
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_product_price_variants_combo
ON product_price_variants(product_id, COALESCE(motor_option_id, ''), COALESCE(channel_option_id, ''));
CREATE INDEX IF NOT EXISTS idx_base_option_groups_product ON product_base_option_groups(product_id, option_type);
CREATE INDEX IF NOT EXISTS idx_base_options_group ON product_base_options(group_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_price_variants_product ON product_price_variants(product_id);

CREATE TABLE IF NOT EXISTS product_specifications (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    label TEXT NOT NULL DEFAULT '',
    label_en TEXT NOT NULL DEFAULT '',
    value TEXT NOT NULL DEFAULT '',
    value_en TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_product_specifications_product ON product_specifications(product_id, sort_order);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    phone TEXT UNIQUE,
    phone_country TEXT,
    password_hash TEXT,
    role TEXT NOT NULL CHECK (role IN ('guest', 'customer', 'sales', 'admin')),
    display_name TEXT NOT NULL DEFAULT '',
    gender TEXT NOT NULL DEFAULT '' CHECK (gender IN ('', 'male', 'female', 'other')),
    birth_date TEXT,
    signature TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    deleted_at TEXT,
    deleted_by TEXT,
    delete_reason TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (role = 'guest' OR email IS NOT NULL OR phone IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS saved_configs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    product_id TEXT NOT NULL REFERENCES products(id),
    snapshot_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'shared', 'quoted', 'closed')),
    version INTEGER NOT NULL DEFAULT 1,
    archived_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS config_shares (
    id TEXT PRIMARY KEY,
    config_id TEXT NOT NULL REFERENCES saved_configs(id) ON DELETE CASCADE,
    code TEXT NOT NULL UNIQUE,
    created_by TEXT NOT NULL REFERENCES users(id),
    expires_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    title TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'zh',
    customer_name TEXT NOT NULL DEFAULT '',
    customer_email TEXT NOT NULL DEFAULT '',
    item_count INTEGER NOT NULL DEFAULT 1,
    view_count INTEGER NOT NULL DEFAULT 0,
    last_viewed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_saved_configs_user ON saved_configs(user_id);
CREATE INDEX IF NOT EXISTS idx_config_shares_config ON config_shares(config_id);
CREATE INDEX IF NOT EXISTS idx_config_shares_expiry ON config_shares(expires_at);

CREATE TABLE IF NOT EXISTS config_share_items (
    id TEXT PRIMARY KEY,
    share_id TEXT NOT NULL REFERENCES config_shares(id) ON DELETE CASCADE,
    config_id TEXT REFERENCES saved_configs(id) ON DELETE SET NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    item_type TEXT NOT NULL DEFAULT 'device_config',
    source_id TEXT,
    display_name TEXT NOT NULL DEFAULT '',
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_config_share_items_share ON config_share_items(share_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_saved_configs_active_user ON saved_configs(user_id, archived_at, updated_at);

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
);
CREATE INDEX IF NOT EXISTS idx_saved_catalog_items_user ON saved_catalog_items(user_id, archived_at, updated_at);

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
);

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
);

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
    quote_number TEXT UNIQUE,
    lifecycle_status TEXT NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,
    valid_until TEXT,
    payment_terms TEXT NOT NULL DEFAULT '',
    delivery_terms TEXT NOT NULL DEFAULT '',
    tax_note TEXT NOT NULL DEFAULT '',
    freight_note TEXT NOT NULL DEFAULT '',
    sales_contact TEXT NOT NULL DEFAULT '',
    quote_note TEXT NOT NULL DEFAULT '',
    sent_at TEXT,
    archived_at TEXT,
    archived_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_commerce_shares_expiry ON commerce_shares(active, expires_at);
CREATE INDEX IF NOT EXISTS idx_commerce_share_items_share ON commerce_share_items(share_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_commerce_quotes_user ON commerce_quotes(user_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_commerce_quotes_lifecycle ON commerce_quotes(lifecycle_status, updated_at);

CREATE TABLE IF NOT EXISTS quote_revisions (
    id TEXT PRIMARY KEY,
    quote_id TEXT NOT NULL REFERENCES commerce_quotes(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL CHECK (revision_number > 0),
    snapshot_json TEXT NOT NULL,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(quote_id, revision_number)
);
CREATE INDEX IF NOT EXISTS idx_quote_revisions_quote ON quote_revisions(quote_id, revision_number DESC);

CREATE TABLE IF NOT EXISTS quote_deliveries (
    id TEXT PRIMARY KEY,
    quote_id TEXT NOT NULL,
    document_version INTEGER NOT NULL DEFAULT 2 CHECK (document_version IN (1, 2)),
    recipient_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_share_id TEXT,
    delivered_by TEXT NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'delivered' CHECK (status IN ('delivered', 'withdrawn')),
    delivered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    viewed_at TEXT,
    withdrawn_at TEXT,
    revision_id TEXT,
    last_viewed_revision_id TEXT,
    notification_state TEXT NOT NULL DEFAULT 'unread',
    UNIQUE(quote_id, recipient_user_id)
);
CREATE INDEX IF NOT EXISTS idx_quote_deliveries_recipient ON quote_deliveries(recipient_user_id, status, delivered_at);
CREATE INDEX IF NOT EXISTS idx_quote_deliveries_quote ON quote_deliveries(quote_id, status);
CREATE INDEX IF NOT EXISTS idx_quote_deliveries_revision ON quote_deliveries(revision_id, status);

CREATE TABLE IF NOT EXISTS customer_inquiries (
    id TEXT PRIMARY KEY,
    inquiry_number TEXT NOT NULL UNIQUE,
    created_by TEXT NOT NULL REFERENCES users(id),
    source_type TEXT NOT NULL CHECK (source_type IN ('current_device', 'cart')),
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'assigned', 'contacted', 'quoted', 'closed', 'cancelled')),
    language TEXT NOT NULL DEFAULT 'zh',
    customer_name_snapshot TEXT NOT NULL DEFAULT '',
    customer_email_snapshot TEXT NOT NULL DEFAULT '',
    customer_phone_snapshot TEXT NOT NULL DEFAULT '',
    customer_country_snapshot TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    item_count INTEGER NOT NULL DEFAULT 0 CHECK (item_count > 0),
    assigned_to TEXT REFERENCES users(id) ON DELETE SET NULL,
    converted_quote_id TEXT REFERENCES commerce_quotes(id) ON DELETE SET NULL,
    idempotency_key TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    contacted_at TEXT,
    quoted_at TEXT,
    closed_at TEXT,
    UNIQUE(created_by, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_customer_inquiries_customer ON customer_inquiries(created_by, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_customer_inquiries_status ON customer_inquiries(status, assigned_to, updated_at DESC);

CREATE TABLE IF NOT EXISTS customer_inquiry_items (
    id TEXT PRIMARY KEY,
    inquiry_id TEXT NOT NULL REFERENCES customer_inquiries(id) ON DELETE CASCADE,
    item_type TEXT NOT NULL CHECK (item_type IN ('device_config', 'tool', 'accessory')),
    source_id TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    display_name TEXT NOT NULL DEFAULT '',
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_customer_inquiry_items_inquiry ON customer_inquiry_items(inquiry_id, sort_order);

CREATE TABLE IF NOT EXISTS share_imports (
    id TEXT PRIMARY KEY,
    share_id TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    idempotency_key TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_share_imports_user ON share_imports(user_id, created_at);

CREATE TABLE IF NOT EXISTS quotes (
    id TEXT PRIMARY KEY,
    config_id TEXT NOT NULL REFERENCES saved_configs(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT '配置报价单',
    items_json TEXT NOT NULL,
    total_price INTEGER NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'CNY',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_quotes_user ON quotes(user_id);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL DEFAULT '',
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at);
"""


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(str(DATABASE_PATH), timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as connection:
        connection.executescript(SCHEMA)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(options)").fetchall()}
        if "notes" not in columns:
            connection.execute("ALTER TABLE options ADD COLUMN notes TEXT NOT NULL DEFAULT ''")
        user_columns = {row[1] for row in connection.execute("PRAGMA table_info(users)").fetchall()}
        if "phone_country" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN phone_country TEXT")
            connection.execute("UPDATE users SET phone_country = 'CN' WHERE phone LIKE '+86%'")
        user_columns = {row[1] for row in connection.execute("PRAGMA table_info(users)").fetchall()}
        for column, definition in (
            ("deleted_at", "TEXT"),
            ("deleted_by", "TEXT"),
            ("delete_reason", "TEXT NOT NULL DEFAULT ''"),
            ("version", "INTEGER NOT NULL DEFAULT 1"),
            ("gender", "TEXT NOT NULL DEFAULT ''"),
            ("birth_date", "TEXT"),
            ("signature", "TEXT NOT NULL DEFAULT ''"),
        ):
            if column not in user_columns:
                connection.execute("ALTER TABLE users ADD COLUMN {} {}".format(column, definition))
        text_columns = (("products", "name_en"), ("products", "title_name_en"), ("products", "description_en"), ("categories", "name_en"), ("categories", "description_en"), ("options", "name_en"), ("options", "description_en"))
        integer_columns = (("products", "price_usd"), ("options", "price_usd"))
        for table, column in text_columns + integer_columns:
            existing = {row[1] for row in connection.execute("PRAGMA table_info(" + table + ")").fetchall()}
            if column not in existing:
                column_type = "INTEGER NOT NULL DEFAULT 0" if (table, column) in integer_columns else "TEXT NOT NULL DEFAULT ''"
                connection.execute("ALTER TABLE {} ADD COLUMN {} {}".format(table, column, column_type))
        qcols = {row[1] for row in connection.execute("PRAGMA table_info(quotes)").fetchall()}
        if "currency" not in qcols:
            connection.execute("ALTER TABLE quotes ADD COLUMN currency TEXT NOT NULL DEFAULT 'CNY'")
        commerce_quote_columns = {row[1] for row in connection.execute("PRAGMA table_info(commerce_quotes)").fetchall()}
        for column, definition in (
            ("quote_number", "TEXT"),
            ("lifecycle_status", "TEXT NOT NULL DEFAULT 'draft'"),
            ("version", "INTEGER NOT NULL DEFAULT 1"),
            ("valid_until", "TEXT"),
            ("payment_terms", "TEXT NOT NULL DEFAULT ''"),
            ("delivery_terms", "TEXT NOT NULL DEFAULT ''"),
            ("tax_note", "TEXT NOT NULL DEFAULT ''"),
            ("freight_note", "TEXT NOT NULL DEFAULT ''"),
            ("sales_contact", "TEXT NOT NULL DEFAULT ''"),
            ("quote_note", "TEXT NOT NULL DEFAULT ''"),
            ("sent_at", "TEXT"),
            ("archived_at", "TEXT"),
            ("archived_by", "TEXT"),
        ):
            if column not in commerce_quote_columns:
                connection.execute("ALTER TABLE commerce_quotes ADD COLUMN {} {}".format(column, definition))
        delivery_columns = {row[1] for row in connection.execute("PRAGMA table_info(quote_deliveries)").fetchall()}
        for column, definition in (
            ("revision_id", "TEXT"),
            ("last_viewed_revision_id", "TEXT"),
            ("notification_state", "TEXT NOT NULL DEFAULT 'unread'"),
        ):
            if column not in delivery_columns:
                connection.execute("ALTER TABLE quote_deliveries ADD COLUMN {} {}".format(column, definition))
        saved_config_columns = {row[1] for row in connection.execute("PRAGMA table_info(saved_configs)").fetchall()}
        for column, definition in (
            ("version", "INTEGER NOT NULL DEFAULT 1"),
            ("archived_at", "TEXT"),
        ):
            if column not in saved_config_columns:
                connection.execute("ALTER TABLE saved_configs ADD COLUMN {} {}".format(column, definition))
        share_columns = {row[1] for row in connection.execute("PRAGMA table_info(config_shares)").fetchall()}
        for column, definition in (
            ("title", "TEXT NOT NULL DEFAULT ''"),
            ("language", "TEXT NOT NULL DEFAULT 'zh'"),
            ("customer_name", "TEXT NOT NULL DEFAULT ''"),
            ("customer_email", "TEXT NOT NULL DEFAULT ''"),
            ("item_count", "INTEGER NOT NULL DEFAULT 1"),
        ):
            if column not in share_columns:
                connection.execute("ALTER TABLE config_shares ADD COLUMN {} {}".format(column, definition))
        connection.execute("""
            INSERT INTO config_share_items (id, share_id, config_id, sort_order, display_name, snapshot_json)
            SELECT lower(hex(randomblob(16))), s.id, s.config_id, 0, c.name, c.snapshot_json
            FROM config_shares s
            JOIN saved_configs c ON c.id = s.config_id
            WHERE NOT EXISTS (SELECT 1 FROM config_share_items i WHERE i.share_id = s.id)
        """)
        mapping_columns = {row[1] for row in connection.execute("PRAGMA table_info(product_options)").fetchall()}
        if "description_override_en" not in mapping_columns:
            connection.execute("ALTER TABLE product_options ADD COLUMN description_override_en TEXT")
        motor_price_columns = {row[1] for row in connection.execute("PRAGMA table_info(product_motor_prices)").fetchall()}
        if "base_price_cny" not in motor_price_columns:
            connection.execute("ALTER TABLE product_motor_prices ADD COLUMN base_price_cny INTEGER NOT NULL DEFAULT 0")
        if "base_price_usd" not in motor_price_columns:
            connection.execute("ALTER TABLE product_motor_prices ADD COLUMN base_price_usd INTEGER NOT NULL DEFAULT 0")
        if "updated_at" not in motor_price_columns:
            connection.execute("ALTER TABLE product_motor_prices ADD COLUMN updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP")
        connection.execute("""
            INSERT OR IGNORE INTO product_motor_prices (product_id, motor_option_id, base_price_cny, base_price_usd)
            SELECT po.product_id, po.option_id, p.base_price, p.price_usd
            FROM product_options po
            JOIN options o ON o.id = po.option_id AND o.category_id = 'motor'
            JOIN products p ON p.id = po.product_id
            WHERE po.enabled = 1
        """)
        connection.execute("PRAGMA optimize")
