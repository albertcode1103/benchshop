import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from alembic.config import Config
from alembic.script import ScriptDirectory

from backend import readiness


def test_readiness_requires_current_schema_without_creating_database():
    config = Config()
    config.set_main_option("script_location", str(Path(readiness.__file__).parent / "migrations"))
    heads = ScriptDirectory.from_config(config).get_heads()
    with TemporaryDirectory() as directory:
        path = Path(directory) / "test.db"
        with patch.object(readiness, "DATABASE_PATH", path):
            assert readiness.database_ready() is False
            assert not path.exists()
            with closing(sqlite3.connect(str(path))) as db, db:
                db.execute("CREATE TABLE alembic_version (version_num TEXT)")
                db.execute("INSERT INTO alembic_version VALUES ('outdated')")
                db.execute("CREATE TABLE products (id INTEGER)")
            assert readiness.database_ready() is False
            with closing(sqlite3.connect(str(path))) as db, db:
                db.execute("DELETE FROM alembic_version")
                db.executemany("INSERT INTO alembic_version VALUES (?)", [(head,) for head in heads])
            assert readiness.database_ready() is True
            with closing(sqlite3.connect(str(path))) as db, db:
                db.execute("DROP TABLE products")
            assert readiness.database_ready() is False
