"""Persistence helpers for administrator and staff operation history."""

import json
import uuid
from typing import Any, Dict, List, Optional

from .database import get_connection


def write_audit(user_id: str, action: str, entity_type: str, entity_id: str = "", details: Optional[Dict[str, Any]] = None) -> None:
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO audit_logs (id, user_id, action, entity_type, entity_id, details_json) VALUES (?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, user_id, action, entity_type, entity_id, json.dumps(details or {}, ensure_ascii=False)),
        )


def list_audit_logs(limit: int = 200) -> List[Dict[str, Any]]:
    safe_limit = min(max(int(limit), 1), 500)
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT a.id, a.user_id, a.action, a.entity_type, a.entity_id,
                   a.details_json, a.created_at, u.display_name, u.email, u.phone, u.role
            FROM audit_logs a
            LEFT JOIN users u ON u.id = a.user_id
            ORDER BY a.created_at DESC, a.rowid DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["details"] = json.loads(item.pop("details_json") or "{}")
        result.append(item)
    return result
