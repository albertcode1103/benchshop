"""Read-only database readiness checks without creating a missing database."""
import sqlite3
from contextlib import closing
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from .config import DATABASE_PATH


def database_ready() -> bool:
    root = Path(__file__).resolve().parent.parent
    config = Config()
    config.set_main_option("script_location", str(root / "backend" / "migrations"))
    expected = set(ScriptDirectory.from_config(config).get_heads())
    try:
        with closing(sqlite3.connect(DATABASE_PATH.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as db:
            actual = {row[0] for row in db.execute("SELECT version_num FROM alembic_version")}
            db.execute("SELECT id FROM products LIMIT 1").fetchall()
            return actual == expected
    except sqlite3.Error:
        return False
