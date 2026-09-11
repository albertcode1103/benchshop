"""Owner-scoped, recoverable record management; never deletes business rows."""
from fastapi import HTTPException
from .database import get_connection
from .security import to_iso, utc_now
from .share_quota import enforce_share_quota


def _owned(db, user_id, kind, resource_id):
    if kind == "shares":
        return any(db.execute(f"SELECT 1 FROM {table} WHERE id=? AND created_by=?", (resource_id, user_id)).fetchone()
                   for table in ("commerce_shares", "config_shares"))
    if kind == "inquiries":
        return db.execute("SELECT 1 FROM customer_inquiries WHERE id=? AND created_by=?", (resource_id, user_id)).fetchone()
    if kind == "quotes":
        return db.execute("SELECT 1 FROM quote_deliveries WHERE quote_id=? AND recipient_user_id=?", (resource_id, user_id)).fetchone()
    return False


def set_visibility(user_id, kind, resource_id, hidden):
    with get_connection() as db:
        db.execute("BEGIN IMMEDIATE")
        if not _owned(db, user_id, kind, resource_id):
            raise HTTPException(404, "记录不存在或无权访问")
        if kind == "shares" and hidden:
            for table in ("commerce_shares", "config_shares"):
                db.execute(f"UPDATE {table} SET owner_closed=CASE WHEN active=1 THEN 1 ELSE owner_closed END, active=0, customer_version=customer_version+1 WHERE id=? AND created_by=? AND active=1", (resource_id, user_id))
        db.execute("""INSERT INTO personal_business_visibility(user_id,resource_type,resource_id,hidden)
            VALUES(?,?,?,?) ON CONFLICT(user_id,resource_type,resource_id)
            DO UPDATE SET hidden=excluded.hidden,updated_at=CURRENT_TIMESTAMP""",
                   (user_id, kind, resource_id, int(hidden)))
    return {"id": resource_id, "hidden": hidden}


def hidden_ids(user_id, kind):
    with get_connection() as db:
        return {row[0] for row in db.execute("SELECT resource_id FROM personal_business_visibility WHERE user_id=? AND resource_type=? AND hidden=1", (user_id, kind))}


def set_owner_share_status(user_id, share_id, active, version):
    with get_connection() as db:
        db.execute("BEGIN IMMEDIATE")
        for table in ("commerce_shares", "config_shares"):
            row = db.execute(f"SELECT active,owner_closed,customer_version,expires_at FROM {table} WHERE id=? AND created_by=?", (share_id, user_id)).fetchone()
            if row is None:
                continue
            if active and not row["active"] and not row["owner_closed"]:
                raise HTTPException(409, "该分享不可由客户重新开启")
            if active and row["expires_at"] <= to_iso(utc_now()):
                raise HTTPException(409, "分享已过期，不能重新开启")
            if bool(row["active"]) == active:
                return {"id": share_id, "active": active, "version": row["customer_version"]}
            if active:
                hidden = db.execute("SELECT hidden FROM personal_business_visibility WHERE user_id=? AND resource_type='shares' AND resource_id=?", (user_id, share_id)).fetchone()
                if hidden and hidden[0]:
                    raise HTTPException(409, "请先恢复已删除的分享记录")
                enforce_share_quota(db, user_id)
            if row["customer_version"] != version:
                raise HTTPException(409, "分享状态已更新，请刷新后重试")
            db.execute(f"UPDATE {table} SET active=?,owner_closed=?,customer_version=customer_version+1 WHERE id=?",
                       (int(active), int(not active), share_id))
            return {"id": share_id, "active": active, "version": version + 1}
    raise HTTPException(404, "分享不存在或无权访问")
