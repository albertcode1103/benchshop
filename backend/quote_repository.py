import json
import uuid
from typing import Any, Dict, List, Optional
from .database import get_connection

def save_quote(config_id: str, user_id: str, title: str, items: List[Dict[str, Any]], total_price: int, quote_id: Optional[str] = None, currency: str = "CNY") -> Dict[str, Any]:
    quote_id = quote_id or uuid.uuid4().hex
    with get_connection() as db:
        exists = db.execute("SELECT id FROM saved_configs WHERE id=?", (config_id,)).fetchone()
        if not exists: raise ValueError("Configuration not found")
        db.execute("""INSERT INTO quotes(id,config_id,user_id,title,items_json,total_price,currency) VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET title=excluded.title,items_json=excluded.items_json,total_price=excluded.total_price,currency=excluded.currency,updated_at=CURRENT_TIMESTAMP""",
                    (quote_id, config_id, user_id, title.strip() or "配置报价单", json.dumps(items, ensure_ascii=False), max(0, int(total_price)), currency))
        row = db.execute("SELECT * FROM quotes WHERE id=?", (quote_id,)).fetchone()
    return _decode(row)

def _decode(row):
    if not row: return None
    result = dict(row); result["items"] = json.loads(result.pop("items_json")); return result

def list_quotes(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as db:
        rows = db.execute("SELECT q.*,u.display_name,u.email,u.phone FROM quotes q JOIN users u ON u.id=q.user_id {} ORDER BY q.updated_at DESC".format("WHERE q.user_id=?" if user_id else ""), ((user_id,) if user_id else ())).fetchall()
    return [_decode(row) for row in rows]

def get_quote(quote_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with get_connection() as db:
        row = db.execute("SELECT * FROM quotes WHERE id=? {}".format("AND user_id=?" if user_id else ""), (quote_id, user_id) if user_id else (quote_id,)).fetchone()
    return _decode(row)

def delete_quote(quote_id: str, user_id: Optional[str] = None) -> bool:
    with get_connection() as db:
        cur = db.execute("DELETE FROM quotes WHERE id=? {}".format("AND user_id=?" if user_id else ""), (quote_id, user_id) if user_id else (quote_id,))
    return cur.rowcount > 0

def list_reference_prices() -> Dict[str, List[Dict[str, Any]]]:
    with get_connection() as db:
        products = db.execute(
            "SELECT id, name, base_price, price_usd FROM products WHERE enabled=1"
        ).fetchall()
        options = db.execute(
            "SELECT id, code, name, price, price_usd FROM options WHERE enabled=1"
        ).fetchall()
    return {
        "products": [dict(row) for row in products],
        "options": [dict(row) for row in options],
    }
