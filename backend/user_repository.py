import uuid
from typing import Any, Dict, List, Optional

from .database import get_connection
from .security import hash_password, hash_token, issue_token, to_iso, utc_now, verify_password
from .phone_countries import get_country
from .account_validation import phone_national
from .account_errors import AccountError


PUBLIC_USER_FIELDS = "id, email, phone, phone_country, role, display_name, gender, birth_date, signature, enabled, deleted_at, deleted_by, delete_reason, version, created_at, updated_at"


def _public(row: Any) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    result = dict(row)
    result.pop("password_hash", None)
    result.pop("should_touch_session", None)
    result["enabled"] = bool(result["enabled"])
    result["archived"] = bool(result.get("deleted_at"))
    country = get_country(result.get("phone_country") or "")
    result["phone"] = phone_national(result.get("phone_country"), result.get("phone"))
    result["phone_calling_code"] = country[3] if country else ""
    return result


def create_user(
    email: Optional[str],
    phone: Optional[str],
    password: Optional[str],
    role: str = "customer",
    display_name: str = "",
    phone_country: Optional[str] = None,
) -> Dict[str, Any]:
    user_id = uuid.uuid4().hex
    encoded = hash_password(password) if password else None
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO users (id, email, phone, phone_country, password_hash, role, display_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, email, phone, phone_country, encoded, role, display_name.strip()),
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
            WHERE (lower(email) = ? OR phone = ?) AND enabled = 1 AND role != 'guest' AND deleted_at IS NULL
            """,
            (normalized, normalized),
        ).fetchone()
    if row is None or not row["password_hash"] or not verify_password(password, row["password_hash"]):
        return None
    return _public(row)


def authenticate_phone(phone: str, password: str) -> Optional[Dict[str, Any]]:
    return authenticate(phone, password)


def verify_user_password(user_id: str, password: str) -> bool:
    with get_connection() as connection:
        row = connection.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    return bool(row and row["password_hash"] and verify_password(password, row["password_hash"]))


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
    token_hash = hash_token(raw_token)
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT u.id, u.email, u.phone, u.phone_country, u.role, u.display_name,
                   u.gender, u.birth_date, u.signature, u.enabled,
                   u.deleted_at, u.deleted_by, u.delete_reason, u.version, u.created_at, u.updated_at,
                   CASE WHEN s.last_seen_at <= datetime('now', '-5 minutes') THEN 1 ELSE 0 END AS should_touch_session
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ? AND u.enabled = 1 AND u.deleted_at IS NULL
            """,
            (token_hash, now),
        ).fetchone()
        if row is not None and row["should_touch_session"]:
            connection.execute(
                "UPDATE sessions SET last_seen_at = CURRENT_TIMESTAMP WHERE token_hash = ?",
                (token_hash,),
            )
    return _public(row)


def revoke_session(raw_token: str) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(raw_token),))

def revoke_user_sessions(user_id: str) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def list_users(
    *,
    archived: bool = False,
    query: str = "",
    role: str = "",
    enabled: Optional[bool] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    clauses = ["role != 'guest'", "deleted_at IS NOT NULL" if archived else "deleted_at IS NULL"]
    parameters: List[Any] = []
    if query.strip():
        pattern = "%{}%".format(query.strip().lower())
        clauses.append("(lower(display_name) LIKE ? OR lower(COALESCE(email, '')) LIKE ? OR phone LIKE ?)")
        parameters.extend([pattern, pattern, pattern])
    if role in ("customer", "sales", "admin"):
        clauses.append("role = ?")
        parameters.append(role)
    if enabled is not None:
        clauses.append("enabled = ?")
        parameters.append(int(enabled))
    sql = "SELECT {} FROM users WHERE {} ORDER BY created_at DESC".format(PUBLIC_USER_FIELDS, " AND ".join(clauses))
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        parameters.extend([limit, max(offset, 0)])
    with get_connection() as connection:
        rows = connection.execute(sql, parameters).fetchall()
    return [_public(row) for row in rows]  # type: ignore


def count_users(*, archived: bool = False, query: str = "", role: str = "", enabled: Optional[bool] = None) -> int:
    clauses = ["role != 'guest'", "deleted_at IS NOT NULL" if archived else "deleted_at IS NULL"]
    parameters: List[Any] = []
    if query.strip():
        pattern = "%{}%".format(query.strip().lower())
        clauses.append("(lower(display_name) LIKE ? OR lower(COALESCE(email, '')) LIKE ? OR phone LIKE ?)")
        parameters.extend([pattern, pattern, pattern])
    if role in ("customer", "sales", "admin"):
        clauses.append("role = ?")
        parameters.append(role)
    if enabled is not None:
        clauses.append("enabled = ?")
        parameters.append(int(enabled))
    with get_connection() as connection:
        row = connection.execute("SELECT COUNT(*) FROM users WHERE {}".format(" AND ".join(clauses)), parameters).fetchone()
    return int(row[0])


def contact_conflict_field(email: Optional[str], phone: Optional[str], exclude_user_id: str = "") -> Optional[str]:
    with get_connection() as connection:
        if email:
            row = connection.execute("SELECT id FROM users WHERE lower(email) = lower(?) AND id != ?", (email, exclude_user_id)).fetchone()
            if row is not None:
                return "email"
        if phone:
            row = connection.execute("SELECT id FROM users WHERE phone = ? AND id != ?", (phone, exclude_user_id)).fetchone()
            if row is not None:
                return "phone"
    return None


def set_user_enabled(user_id: str, enabled: bool, expected_version: Optional[int] = None) -> Optional[Dict[str, Any]]:
    with get_connection() as connection:
        if expected_version is None:
            cursor = connection.execute(
                "UPDATE users SET enabled = ?, version = version + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND deleted_at IS NULL",
                (int(enabled), user_id),
            )
        else:
            cursor = connection.execute(
                "UPDATE users SET enabled = ?, version = version + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND version = ? AND deleted_at IS NULL",
                (int(enabled), user_id, expected_version),
            )
        if cursor.rowcount == 0:
            exists = connection.execute("SELECT 1 FROM users WHERE id = ? AND deleted_at IS NULL", (user_id,)).fetchone()
            if exists is not None:
                raise AccountError("ACCOUNT_VERSION_CONFLICT", status_code=409)
            return None
        if not enabled:
            connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        row = connection.execute(
            "SELECT {} FROM users WHERE id = ?".format(PUBLIC_USER_FIELDS), (user_id,)
        ).fetchone()
    return _public(row)

def update_user(user_id: str, values: Dict[str, Any], expected_version: Optional[int] = None) -> Optional[Dict[str, Any]]:
    allowed = {"email", "phone", "phone_country", "display_name", "gender", "birth_date", "signature", "role", "password"}
    values = {k: v for k, v in values.items() if k in allowed}
    password_changed = bool(values.get("password"))
    if password_changed:
        values["password_hash"] = hash_password(values.pop("password"))
    else:
        values.pop("password", None)
    if not values: return get_user_by_id(user_id)
    with get_connection() as connection:
        existing = connection.execute("SELECT * FROM users WHERE id = ? AND deleted_at IS NULL", (user_id,)).fetchone()
        if existing is None:
            return None
        sensitive_fields = {"email", "phone", "phone_country", "role", "password_hash"}
        sensitive_changed = password_changed or any(key in sensitive_fields and values[key] != existing[key] for key in values)
        fields = ", ".join(f"{k} = ?" for k in values) + ", version = version + 1, updated_at = CURRENT_TIMESTAMP"
        parameters = [*values.values(), user_id]
        version_clause = ""
        if expected_version is not None:
            version_clause = " AND version = ?"
            parameters.append(expected_version)
        cursor = connection.execute(f"UPDATE users SET {fields} WHERE id = ? AND deleted_at IS NULL{version_clause}", parameters)
        if cursor.rowcount == 0:
            raise AccountError("ACCOUNT_VERSION_CONFLICT", status_code=409)
        row = connection.execute("SELECT {} FROM users WHERE id = ?".format(PUBLIC_USER_FIELDS), (user_id,)).fetchone()
        if sensitive_changed:
            connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    return _public(row)


def archive_user(user_id: str, archived_by: str, reason: str, expected_version: int) -> Optional[Dict[str, Any]]:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE users
            SET enabled = 0, deleted_at = CURRENT_TIMESTAMP, deleted_by = ?, delete_reason = ?,
                version = version + 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND version = ? AND deleted_at IS NULL
            """,
            (archived_by, reason.strip(), user_id, expected_version),
        )
        if cursor.rowcount == 0:
            existing = connection.execute("SELECT deleted_at FROM users WHERE id = ?", (user_id,)).fetchone()
            if existing is None:
                return None
            if existing[0]:
                raise AccountError("ACCOUNT_ARCHIVED", status_code=409)
            raise AccountError("ACCOUNT_VERSION_CONFLICT", status_code=409)
        connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        row = connection.execute("SELECT {} FROM users WHERE id = ?".format(PUBLIC_USER_FIELDS), (user_id,)).fetchone()
    return _public(row)


def restore_user(user_id: str, expected_version: int) -> Optional[Dict[str, Any]]:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE users
            SET enabled = 1, deleted_at = NULL, deleted_by = NULL, delete_reason = '',
                version = version + 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND version = ? AND deleted_at IS NOT NULL
            """,
            (user_id, expected_version),
        )
        if cursor.rowcount == 0:
            existing = connection.execute("SELECT deleted_at FROM users WHERE id = ?", (user_id,)).fetchone()
            if existing is None:
                return None
            if not existing[0]:
                raise AccountError("ACCOUNT_NOT_ARCHIVED", status_code=409)
            raise AccountError("ACCOUNT_VERSION_CONFLICT", status_code=409)
        row = connection.execute("SELECT {} FROM users WHERE id = ?".format(PUBLIC_USER_FIELDS), (user_id,)).fetchone()
    return _public(row)

def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as connection:
        row = connection.execute("SELECT {} FROM users WHERE id = ?".format(PUBLIC_USER_FIELDS), (user_id,)).fetchone()
    return _public(row)
