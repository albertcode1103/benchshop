"""Safe backup, verification and restore commands for the BOTEN SQLite database."""

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import DATABASE_PATH, PROJECT_DIR
from .database import initialize_database


DEFAULT_BACKUP_DIR = PROJECT_DIR / "backups"


def verify_database(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError("Database file not found: {}".format(path))
    connection = sqlite3.connect(str(path))
    try:
        result = connection.execute("PRAGMA quick_check").fetchone()
    finally:
        connection.close()
    if not result or result[0] != "ok":
        raise RuntimeError("SQLite integrity check failed: {}".format(result[0] if result else "unknown"))


def create_backup(output_dir: Path = DEFAULT_BACKUP_DIR, keep: int = 30) -> Path:
    source = DATABASE_PATH.resolve()
    verify_database(source)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    destination = output_dir / "boten-{}.db".format(stamp)

    source_connection = sqlite3.connect(str(source))
    destination_connection = sqlite3.connect(str(destination))
    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()
    verify_database(destination)

    if keep > 0:
        backups = sorted(output_dir.glob("boten-*.db"), key=lambda path: path.stat().st_mtime, reverse=True)
        for expired in backups[keep:]:
            if expired.resolve().parent != output_dir:
                raise RuntimeError("Refusing to remove a backup outside {}".format(output_dir))
            expired.unlink()
    return destination


def restore_backup(source: Path, confirmation: str, safety_dir: Path = DEFAULT_BACKUP_DIR) -> Path:
    if confirmation != "RESTORE":
        raise ValueError("Restore requires --confirm RESTORE")
    source = source.resolve()
    target = DATABASE_PATH.resolve()
    if source == target:
        raise ValueError("Backup source and active database cannot be the same file")
    verify_database(source)

    safety_backup: Optional[Path] = None
    if target.exists():
        safety_backup = create_backup(safety_dir, keep=0)

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".restore-tmp")
    if temporary.exists():
        temporary.unlink()
    try:
        source_connection = sqlite3.connect(str(source))
        target_connection = sqlite3.connect(str(temporary))
        try:
            source_connection.backup(target_connection)
        finally:
            target_connection.close()
            source_connection.close()
        verify_database(temporary)
        temporary.replace(target)
        verify_database(target)
        initialize_database()
    finally:
        if temporary.exists():
            temporary.unlink()
    return safety_backup or target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maintain the BOTEN SQLite database")
    commands = parser.add_subparsers(dest="command", required=True)

    backup = commands.add_parser("backup", help="Create and verify an online SQLite backup")
    backup.add_argument("--output-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    backup.add_argument("--keep", type=int, default=30, help="Number of newest backups to keep; 0 keeps all")

    check = commands.add_parser("check", help="Run SQLite quick_check")
    check.add_argument("path", nargs="?", type=Path, default=DATABASE_PATH)

    restore = commands.add_parser("restore", help="Restore a verified backup")
    restore.add_argument("source", type=Path)
    restore.add_argument("--confirm", required=True, help="Must be exactly RESTORE")
    restore.add_argument("--safety-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    return parser


def main() -> None:
    arguments = build_parser().parse_args()
    if arguments.command == "backup":
        result = create_backup(arguments.output_dir, max(0, arguments.keep))
        print("Backup created: {}".format(result))
    elif arguments.command == "check":
        verify_database(arguments.path.resolve())
        print("Database check passed: {}".format(arguments.path.resolve()))
    else:
        safety = restore_backup(arguments.source, arguments.confirm, arguments.safety_dir)
        print("Restore completed. Pre-restore safety backup: {}".format(safety))


if __name__ == "__main__":
    main()
