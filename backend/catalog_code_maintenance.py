"""Preview or apply canonical catalog codes and remove duplicate code name prefixes."""

import argparse
import shutil
from datetime import datetime
from pathlib import Path

from .catalog_identity import normalize_catalog_code, strip_redundant_catalog_code
from .database import DATABASE_PATH, get_connection


def normalize_catalog_records(apply: bool = False):
    with get_connection() as db:
        rows = db.execute(
            """SELECT o.id, o.code, o.name, o.name_en
               FROM options o JOIN categories c ON c.id = o.category_id
               WHERE o.deleted_at IS NULL
                 AND c.catalog_type IN ('optional', 'tools', 'accessories')"""
        ).fetchall()
        changes = []
        normalized_by_id = {row["id"]: normalize_catalog_code(row["code"]) for row in rows}
        duplicates = db.execute(
            """SELECT lower(trim(code)) AS normalized, COUNT(*) AS count
               FROM options WHERE deleted_at IS NULL GROUP BY lower(trim(code)) HAVING COUNT(*) > 1"""
        ).fetchall()
        existing_duplicates = {row["normalized"] for row in duplicates}
        targets = {}
        for option_id, code in normalized_by_id.items():
            key = code.casefold()
            if key in targets and targets[key] != option_id:
                raise RuntimeError("normalized catalog code collision: {}".format(code))
            targets[key] = option_id
        for row in rows:
            old_code = row["code"] or ""
            code = normalized_by_id[row["id"]]
            name = strip_redundant_catalog_code(row["name"], code, (old_code,))
            name_en = strip_redundant_catalog_code(row["name_en"], code, (old_code,))
            if (code, name, name_en) != (old_code, row["name"] or "", row["name_en"] or ""):
                changes.append({"id": row["id"], "old_code": old_code, "code": code, "name": name, "name_en": name_en})
        if apply and changes:
            for item in changes:
                db.execute(
                    "UPDATE options SET code = ?, name = ?, name_en = ?, version = version + 1 WHERE id = ?",
                    (item["code"], item["name"], item["name_en"], item["id"]),
                )
        return changes, existing_duplicates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        backup_dir = Path(DATABASE_PATH).parent.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / "boten-catalog-code-{}.db".format(datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
        shutil.copy2(DATABASE_PATH, backup)
        print("backup={}".format(backup))
    changes, existing_duplicates = normalize_catalog_records(args.apply)
    print("mode={} changes={} preexisting_duplicate_codes={}".format("apply" if args.apply else "preview", len(changes), len(existing_duplicates)))
    for item in changes:
        print("{}: {} -> {} | {} | {}".format(item["id"], item["old_code"], item["code"], item["name"], item["name_en"]))


if __name__ == "__main__":
    main()
