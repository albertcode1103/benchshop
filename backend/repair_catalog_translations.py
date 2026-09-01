"""Safely restore catalog translation fields from a known-good SQLite backup.

Only bilingual catalog text is restored. Prices, images, product-option mappings,
motor prices, specifications, users, saved configurations and quotes are preserved.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE = PROJECT_DIR / "backend" / "boten.db"
DEFAULT_SOURCE = PROJECT_DIR / "backups" / "boten-20260831-134152-314467.db"

TABLES = {
    "products": ("id", ("name", "name_en", "title_name", "title_name_en", "description", "description_en")),
    "categories": ("id", ("name", "name_en", "description", "description_en")),
    "options": ("id", ("name", "name_en", "description", "description_en")),
    "product_colors": (("product_id", "code"), ("label", "label_en")),
}


def quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def key_where(key):
    keys = (key,) if isinstance(key, str) else key
    return " AND ".join(f"{quoted(column)} = ?" for column in keys), keys


def restore(database: Path, source: Path, apply: bool) -> dict[str, int]:
    if not database.exists():
        raise FileNotFoundError(f"Database not found: {database}")
    if not source.exists():
        raise FileNotFoundError(f"Backup not found: {source}")

    source_db = sqlite3.connect(source)
    target_db = sqlite3.connect(database)
    result = {"rows": 0, "fields": 0, "backup": ""}
    try:
        if apply:
            backup_dir = database.parent.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / f"boten-before-translation-repair-{datetime.now():%Y%m%d-%H%M%S}.db"
            shutil.copy2(database, backup)
            result["backup"] = str(backup)
            target_db.execute("BEGIN IMMEDIATE")

        for table, (key, fields) in TABLES.items():
            key_columns = (key,) if isinstance(key, str) else key
            columns = (*key_columns, *fields)
            source_rows = source_db.execute(
                f"SELECT {', '.join(quoted(column) for column in columns)} FROM {quoted(table)}"
            ).fetchall()
            where, _ = key_where(key)
            for row in source_rows:
                values = dict(zip(columns, row))
                target = target_db.execute(
                    f"SELECT {', '.join(quoted(column) for column in fields)} FROM {quoted(table)} WHERE {where}",
                    tuple(values[column] for column in key_columns),
                ).fetchone()
                if target is None:
                    continue
                changed = [field for index, field in enumerate(fields) if target[index] != values[field]]
                if not changed:
                    continue
                result["rows"] += 1
                result["fields"] += len(changed)
                if apply:
                    assignments = ", ".join(f"{quoted(field)} = ?" for field in fields)
                    target_db.execute(
                        f"UPDATE {quoted(table)} SET {assignments} WHERE {where}",
                        tuple(values[field] for field in fields) + tuple(values[column] for column in key_columns),
                    )

        if apply:
            target_db.commit()
        return result
    except Exception:
        if apply:
            target_db.rollback()
        raise
    finally:
        source_db.close()
        target_db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore only catalog translation text from a backup database.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--apply", action="store_true", help="Apply changes; omit for a dry-run report.")
    args = parser.parse_args()
    result = restore(args.database, args.source, args.apply)
    mode = "Applied" if args.apply else "Dry run"
    print(f"{mode}: {result['rows']} rows, {result['fields']} text fields.")
    if result["backup"]:
        print(f"Safety backup: {result['backup']}")


if __name__ == "__main__":
    main()
