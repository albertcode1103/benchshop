"""Safe catalog upload reference checks and orphan cleanup."""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from .config import UPLOAD_DIR
from .database import get_connection
from .media_routes import MEDIA_NAME


REFERENCE_COLUMNS = (
    ("product_colors", "image_path"),
    ("options", "image_path"),
    ("product_options", "image_override"),
    ("product_images", "image_path"),
)


def _media_name(value: Any) -> Optional[str]:
    path = str(value or "").strip()
    prefix = "/api/v1/media/"
    if not path.startswith(prefix):
        return None
    name = path[len(prefix):]
    return name if MEDIA_NAME.fullmatch(name) else None


def referenced_media_names() -> Set[str]:
    names: Set[str] = set()
    with get_connection() as database:
        tables = {row[0] for row in database.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        for table, column in REFERENCE_COLUMNS:
            if table not in tables:
                continue
            columns = {row[1] for row in database.execute("PRAGMA table_info({})".format(table))}
            if column not in columns:
                continue
            for row in database.execute("SELECT {} FROM {} WHERE {} IS NOT NULL".format(column, table, column)):
                name = _media_name(row[0])
                if name:
                    names.add(name)
    return names


def orphan_uploads(upload_dir: Path = UPLOAD_DIR) -> List[Path]:
    root = upload_dir.resolve()
    if not root.is_dir():
        return []
    referenced = referenced_media_names()
    return sorted(
        path for path in root.iterdir()
        if path.is_file() and MEDIA_NAME.fullmatch(path.name) and path.name not in referenced
    )


def remove_unreferenced_media(paths: Iterable[str], upload_dir: Path = UPLOAD_DIR) -> List[str]:
    root = upload_dir.resolve()
    referenced = referenced_media_names()
    removed: List[str] = []
    for value in paths:
        name = _media_name(value)
        if not name or name in referenced:
            continue
        candidate = (root / name).resolve()
        if candidate.parent != root or not candidate.is_file():
            continue
        candidate.unlink()
        removed.append(name)
    return removed


def cleanup_orphan_uploads(apply: bool = False, upload_dir: Path = UPLOAD_DIR) -> Dict[str, Any]:
    candidates = orphan_uploads(upload_dir)
    removed: List[str] = []
    if apply:
        removed = remove_unreferenced_media(
            ["/api/v1/media/{}".format(path.name) for path in candidates], upload_dir
        )
    return {
        "mode": "apply" if apply else "preview",
        "upload_dir": str(upload_dir.resolve()),
        "candidates": [path.name for path in candidates],
        "removed": removed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview or remove orphan BOTEN catalog uploads")
    parser.add_argument("cleanup", nargs="?", default="cleanup", choices=("cleanup",))
    parser.add_argument("--apply", action="store_true", help="Delete candidates; default is preview only")
    arguments = parser.parse_args()
    print(json.dumps(cleanup_orphan_uploads(arguments.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
