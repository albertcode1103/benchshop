import uuid
from typing import Any, Dict, List, Optional

from .database import get_connection
from .security import hash_password, hash_token, issue_token, to_iso, utc_now, verify_password


PUBLIC_USER_FIELDS = "id, email, phone, role, display_name, enabled, created_at, updated_at"


def _public(row: Any) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    result = dict(row)
    result.pop("password_hash", None)
    result["enabled"] = bool(result["enabled"])
    return result


def create_user(
    email: Optional[str],
    phone: Optional[str],
    password: Optional[str],
    role: str = "customer",
    display_name: str = "",
) -> Dict[str, Any]:
    user_id = uuid.uuid4().hex
    encoded = hash_password(password) if password else None
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO users (id, email, phone, password_hash, role, display_name)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, email, phone, encoded, role, display_name.strip()),
        )
        row = connection.execute(
            "SELECT {} FROM users WHERE id = ?".format(PUBLIC_USER_FIELDS), (user_id,)
        ).fetchone()
    return _public(row)  # type: ignore


def create_guest() -> Dict[str, Any]:
    return create_user(None, None, None, role="guest", display_name="游客")


def authenticate(identifier: str, password: str) -> Optional[Dict[str, Any]]:
    normalized = identifier.strip().lower()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT * FROM users
            WHERE (lower(email) = ? OR phone = ?) AND enabled = 1 AND role != 'guest'
            """,
            (normalized, normalized),
        ).fetchone()
    if row is None or not row["password_hash"] or not verify_password(password, row["password_hash"]):
        return None
    return _public(row)


def create_session(user: Dict[str, Any]) -> Dict[str, str]:
    raw_token, token_hash_value, expires_at = issue_token(user["role"] == "guest")
    session_id = uuid.uuid4().hex
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO sessions (id, user_id, token_hash, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, user["id"], token_hash_value, expires_at),
        )
    return {"token": raw_token, "token_type": "bearer", "expires_at": expires_at}


def get_user_by_token(raw_token: str) -> Optional[Dict[str, Any]]:
    now = to_iso(utc_now())
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT u.id, u.email, u.phone, u.role, u.display_name, u.enabled,
                   u.created_at, u.updated_at
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ? AND u.enabled = 1
            """,
            (hash_token(raw_token), now),
        ).fetchone()
        if row is not None:
            connection.execute(
                "UPDATE sessions SET last_seen_at = CURRENT_TIMESTAMP WHERE token_hash = ?",
                (hash_token(raw_token),),
            )
    return _public(row)


def revoke_session(raw_token: str) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(raw_token),))


def list_users() -> List[Dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT {} FROM users WHERE role != 'guest' ORDER BY created_at DESC".format(PUBLIC_USER_FIELDS)
        ).fetchall()
    return [_public(row) for row in rows]  # type: ignore


def set_user_enabled(user_id: str, enabled: bool) -> Optional[Dict[str, Any]]:
    with get_connection() as connection:
        connection.execute(
            "UPDATE users SET enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (int(enabled), user_id),
        )
        if not enabled:
            connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        row = connection.execute(
            "SELECT {} FROM users WHERE id = ?".format(PUBLIC_USER_FIELDS), (user_id,)
        ).fetchone()
    return _public(row)

def update_user(user_id: str, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed = {"email", "phone", "display_name", "role", "password"}
    values = {k: v for k, v in values.items() if k in allowed and v is not None}
    if values.get("password"):
        values["password_hash"] = hash_password(values.pop("password"))
    else:
        values.pop("password", None)
    if not values: return get_user_by_id(user_id)
    fields = ", ".join(f"{k} = ?" for k in values) + ", updated_at = CURRENT_TIMESTAMP"
    with get_connection() as connection:
        connection.execute(f"UPDATE users SET {fields} WHERE id = ?", (*values.values(), user_id))
        row = connection.execute("SELECT {} FROM users WHERE id = ?".format(PUBLIC_USER_FIELDS), (user_id,)).fetchone()
    return _public(row)

def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as connection:
        row = connection.execute("SELECT {} FROM users WHERE id = ?".format(PUBLIC_USER_FIELDS), (user_id,)).fetchone()
    return _public(row)
