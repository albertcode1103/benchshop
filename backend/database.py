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
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_colors (
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    label TEXT NOT NULL,
    image_path TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (product_id, code)
);

CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_en TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    description_en TEXT NOT NULL DEFAULT '',
    multiple INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0
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
    notes TEXT NOT NULL DEFAULT '',
    price INTEGER NOT NULL DEFAULT 0,
    price_usd INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0
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

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    phone TEXT UNIQUE,
    password_hash TEXT,
    role TEXT NOT NULL CHECK (role IN ('guest', 'customer', 'sales', 'admin')),
    display_name TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
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
    view_count INTEGER NOT NULL DEFAULT 0,
    last_viewed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_saved_configs_user ON saved_configs(user_id);
CREATE INDEX IF NOT EXISTS idx_config_shares_config ON config_shares(config_id);
CREATE INDEX IF NOT EXISTS idx_config_shares_expiry ON config_shares(expires_at);

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
    connection = sqlite3.connect(str(DATABASE_PATH))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
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
        mapping_columns = {row[1] for row in connection.execute("PRAGMA table_info(product_options)").fetchall()}
        if "description_override_en" not in mapping_columns:
            connection.execute("ALTER TABLE product_options ADD COLUMN description_override_en TEXT")
        connection.execute("PRAGMA optimize")
