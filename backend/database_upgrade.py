"""Single database upgrade entry point for local and container startup."""
import sqlite3
from contextlib import closing
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from .config import DATABASE_PATH


def upgrade_database():
    root = Path(__file__).resolve().parent.parent
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "backend" / "migrations"))
    expected = set(ScriptDirectory.from_config(config).get_heads())
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DATABASE_PATH.exists():
        with closing(sqlite3.connect(str(DATABASE_PATH))) as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if tables and "alembic_version" not in tables:
                raise RuntimeError("Existing database has no migration version; explicit baseline reconciliation is required")
            actual = {row[0] for row in db.execute("SELECT version_num FROM alembic_version")} if "alembic_version" in tables else set()
        if actual == expected:
            return
        if tables:
            from .database_maintenance import create_backup
            create_backup(DATABASE_PATH.parent / "migration-backups", keep=0)
    command.upgrade(config, "head")
    with closing(sqlite3.connect(str(DATABASE_PATH))) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Database integrity check failed after upgrade")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise RuntimeError("Database foreign key check failed after upgrade")


if __name__ == "__main__":
    upgrade_database()
