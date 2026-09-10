import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path


def test_legacy_and_drifted_upgrade_preserves_data_and_backups(tmp_path):
    root = Path(__file__).resolve().parents[1]
    path = tmp_path / "upgrade.db"
    env = dict(os.environ, BOTEN_DATABASE_PATH=str(path))

    def run(*args):
        result = subprocess.run([sys.executable, *args], cwd=root, env=env,
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr

    run("-m", "alembic", "upgrade", "20260905_0018")
    with closing(sqlite3.connect(str(path))) as db, db:
        db.execute("CREATE TABLE upgrade_sentinel (value TEXT)")
        db.execute("INSERT INTO upgrade_sentinel VALUES ('preserve me')")
    run("-m", "backend.database_upgrade")
    assert len(list((tmp_path / "migration-backups").glob("*.db"))) == 1
    # Simulate the old initializer having added fields without advancing version.
    with closing(sqlite3.connect(str(path))) as db, db:
        db.execute("UPDATE alembic_version SET version_num = '20260905_0018'")
    run("-m", "backend.database_upgrade")
    assert len(list((tmp_path / "migration-backups").glob("*.db"))) == 2
    run("-m", "backend.database_upgrade")
    assert len(list((tmp_path / "migration-backups").glob("*.db"))) == 2
    with closing(sqlite3.connect(str(path))) as db:
        assert db.execute("SELECT value FROM upgrade_sentinel").fetchall() == [('preserve me',)]
        assert db.execute("PRAGMA integrity_check").fetchone() == ('ok',)
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ('20260911_0026',)
