"""Recovery rehearsal against the real 0030 migration chain and synthetic data."""

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from contextlib import closing

import pytest
from backend.database_maintenance import replace_verified_database
from deploy.release_bundle import database_info, digest


ROOT = Path(__file__).resolve().parents[1]


def _initialize_0030(database: Path) -> None:
    environment = os.environ | {"BOTEN_DATABASE_PATH": str(database)}
    subprocess.run(
        [sys.executable, "-c", "from backend.database import initialize_database; initialize_database()"],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def _backup(source: Path, target: Path) -> None:
    with closing(sqlite3.connect(source)) as read_connection, closing(sqlite3.connect(target)) as write_connection:
        read_connection.backup(write_connection)


def _atomic_restore(source: Path, target: Path) -> None:
    temporary = target.with_suffix(".restore-tmp")
    _backup(source, temporary)
    with closing(sqlite3.connect(temporary)) as connection:
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    replace_verified_database(temporary, target)


def test_0030_synthetic_database_backup_and_recovery_rehearsal(tmp_path):
    source = tmp_path / "source-0030.db"
    _initialize_0030(source)
    upload = tmp_path / "uploads" / "recovery.png"
    upload.parent.mkdir()
    upload.write_bytes(b"synthetic-image-content")
    with closing(sqlite3.connect(source)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "INSERT INTO products (id, name, title_name) VALUES (?, ?, ?)",
            ("cr1016", "Synthetic product", "Synthetic product"),
        )
        connection.execute(
            "INSERT INTO users (id, email, role, display_name) VALUES (?, ?, ?, ?)",
            ("recovery-user", "recovery@example.test", "customer", "Recovery User"),
        )
        connection.execute(
            "INSERT INTO saved_configs (id, user_id, name, product_id, snapshot_json) VALUES (?, ?, ?, ?, ?)",
            ("recovery-config", "recovery-user", "Synthetic recovery", "cr1016", "{}"),
        )
        connection.execute(
            "INSERT INTO commerce_shares (id, code, created_by, expires_at, primary_config_id) VALUES (?, ?, ?, ?, ?)",
            ("recovery-share", "654321", "recovery-user", "2099-01-01T00:00:00+00:00", "recovery-config"),
        )
        connection.execute(
            "INSERT INTO commerce_share_items (id, share_id, item_type, source_id, snapshot_json) VALUES (?, ?, ?, ?, ?)",
            ("recovery-item", "recovery-share", "device_config", "recovery-config", json.dumps({"image": "/api/v1/media/recovery.png"})),
        )
        connection.commit()
    version, before_counts, references = database_info(source)
    assert version == "20260911_0030"
    assert "commerce_shares" in before_counts and before_counts["commerce_shares"] == 1
    assert references == {"api/v1/media/recovery.png"}

    backup = tmp_path / "backup.db"
    _backup(source, backup)
    destination = tmp_path / "destination.db"
    with closing(sqlite3.connect(destination)) as connection:
        connection.execute("CREATE TABLE pre_recovery_marker (value TEXT)")
        connection.execute("INSERT INTO pre_recovery_marker VALUES ('sentinel')")
        connection.commit()
    sentinel_hash = digest(destination)

    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"not a sqlite database")
    with pytest.raises(sqlite3.DatabaseError):
        with sqlite3.connect(corrupt) as connection:
            connection.execute("PRAGMA quick_check").fetchone()
    assert digest(destination) == sentinel_hash

    _atomic_restore(backup, destination)
    restored_version, restored_counts, restored_refs = database_info(destination)
    assert (restored_version, restored_counts, restored_refs) == (version, before_counts, references)
    assert digest(upload) == digest(tmp_path / "uploads" / "recovery.png")
