"""Shared quota checks. Call enforcement inside the caller's write transaction."""
from .account_errors import AccountError
from .security import to_iso, utc_now

SHARE_LIMIT = 10


def share_quota(db, user_id):
    user = db.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
    if user is None:
        raise AccountError("ACCOUNT_NOT_FOUND", status_code=404)
    now = to_iso(utc_now())
    used = sum(db.execute(f"SELECT count(*) FROM {table} WHERE created_by=? AND active=1 AND expires_at>?", (user_id, now)).fetchone()[0]
               for table in ("commerce_shares", "config_shares"))
    limited = user["role"] == "customer"
    return {"used": used, "limit": SHARE_LIMIT if limited else None,
            "remaining": max(0, SHARE_LIMIT - used) if limited else None, "limited": limited}


def enforce_share_quota(db, user_id):
    quota = share_quota(db, user_id)
    if quota["limited"] and quota["used"] >= SHARE_LIMIT:
        raise AccountError("SHARE_QUOTA_EXCEEDED", status_code=409, params={"limit": SHARE_LIMIT, "used": quota["used"]})
    return quota
