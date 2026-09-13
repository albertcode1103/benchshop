"""Bounded summaries over all business records; never uses a list page as a total."""

from datetime import timedelta, timezone

from .database import get_connection
from .dashboard_rules import INQUIRY_BUSINESS_SQL, QUOTE_DUE_SQL, QUOTE_EXPIRY_SQL, inquiry_queue_clause, utc_now


SHARES_SQL = """
    SELECT s.id, s.code, c.name, s.active, s.expires_at, s.view_count, s.created_at, 1 AS document_version
    FROM config_shares s JOIN saved_configs c ON c.id=s.config_id JOIN users u ON u.id=s.created_by
    UNION ALL
    SELECT s.id, s.code, s.title AS name, s.active, s.expires_at, s.view_count, s.created_at, 2 AS document_version
    FROM commerce_shares s JOIN users u ON u.id=s.created_by
"""
QUOTES_SQL = """
    SELECT q.id, q.user_id, q.quote_number, q.title, q.customer_name, q.lifecycle_status,
           q.valid_until, q.created_at, q.updated_at, 2 AS document_version
    FROM commerce_quotes q JOIN users u ON u.id=q.user_id
    UNION ALL
    SELECT q.id, q.user_id, NULL AS quote_number, q.title, '' AS customer_name, 'draft' AS lifecycle_status,
           NULL AS valid_until, q.created_at, q.updated_at, 1 AS document_version
    FROM quotes q JOIN users u ON u.id=q.user_id
"""
INQUIRIES_SQL = """
    SELECT i.id, i.inquiry_number, i.status, i.assigned_to,
           COALESCE(NULLIF(i.customer_name_snapshot,''),creator.display_name) AS customer_name,
           assignee.display_name AS assignee_name, i.created_at,
           COALESCE(NULLIF(i.updated_at,''),i.created_at) AS updated_at,
           """ + INQUIRY_BUSINESS_SQL + """ AS business_status
    FROM customer_inquiries i JOIN users creator ON creator.id=i.created_by
    LEFT JOIN users assignee ON assignee.id=i.assigned_to WHERE 1=1
"""


def dashboard(user, days=30):
    if days not in (7, 30):
        raise ValueError('days must be 7 or 30')
    now = utc_now()
    today = now.astimezone(timezone(timedelta(hours=8))).date()
    dates = [(today - timedelta(days=offset)).isoformat() for offset in reversed(range(days))]
    admin = user['role'] == 'admin'
    owner_clause, owner_params = ('', ()) if admin else (' WHERE user_id=?', (user['id'],))
    quotes_sql = 'SELECT * FROM (' + QUOTES_SQL + ')' + owner_clause
    follow_clause, follow_params = inquiry_queue_clause(user['id'], user['role'], 'followup', now)
    stale_clause, stale_params = inquiry_queue_clause(user['id'], user['role'], 'stale', now)
    follow_sql, stale_sql = INQUIRIES_SQL + follow_clause, INQUIRIES_SQL + stale_clause
    due_sql = 'SELECT * FROM (' + quotes_sql + ') WHERE ' + QUOTE_DUE_SQL
    due_params = (*owner_params, now.isoformat(), now.isoformat())
    draft_sql = 'SELECT * FROM (' + quotes_sql + ") WHERE lifecycle_status='draft'"
    with get_connection() as db:
        # A single read snapshot keeps counters, snippets and trends consistent.
        db.execute('BEGIN')

        def count(sql, params=()):
            return db.execute('SELECT COUNT(*) FROM (' + sql + ')', params).fetchone()[0]

        def recent(sql, params=(), order='julianday(created_at) DESC, id DESC'):
            return [dict(row) for row in db.execute('SELECT * FROM (' + sql + ') ORDER BY ' + order + ' LIMIT 5', params)]

        def trend(sql, params=()):
            counts = dict(db.execute("SELECT date(created_at,'+8 hours'), COUNT(*) FROM (" + sql +
                ") WHERE date(created_at,'+8 hours') BETWEEN ? AND ? GROUP BY date(created_at,'+8 hours')",
                (*params, dates[0], dates[-1])).fetchall())
            return [counts.get(date, 0) for date in dates]

        result = {
            'generated_at': now.isoformat(), 'days': days, 'timezone': 'Asia/Shanghai',
            'scopes': {'inquiries': '公共询价', 'shares': '公共分享',
                       'quotes': '全部报价' if admin else '我的报价',
                       'tasks': '全部待跟进询价' if admin else '分配给我的询价'},
            'counts': {'followup': count(follow_sql, follow_params), 'stale': count(stale_sql, stale_params),
                       'drafts': count(draft_sql, owner_params), 'due': count(due_sql, due_params)},
            'tasks': {'inquiries': recent(follow_sql, follow_params, 'julianday(updated_at), id'),
                      'drafts': recent(draft_sql, owner_params, 'julianday(updated_at) DESC, id DESC'),
                      'due': recent(due_sql, due_params, '(' + QUOTE_EXPIRY_SQL + '), id')},
            'trend': {'dates': dates, 'inquiries': trend(INQUIRIES_SQL),
                      'quotes': trend(quotes_sql, owner_params), 'shares': trend(SHARES_SQL)},
            'recent': {'inquiries': recent(INQUIRIES_SQL),
                       'quotes': recent(quotes_sql, owner_params, 'julianday(updated_at) DESC, id DESC'),
                       'shares': recent(SHARES_SQL)},
        }
        for share in result['recent']['shares']:
            expired = db.execute('SELECT julianday(?) <= julianday(?)', (share['expires_at'], now.isoformat())).fetchone()[0]
            share['status'] = 'closed' if not share['active'] else 'expired' if expired else 'active'
        share_metrics = db.execute("SELECT COALESCE(SUM(CASE WHEN active=1 AND julianday(expires_at)>julianday(?) THEN 1 ELSE 0 END),0), COALESCE(SUM(view_count),0) FROM (" + SHARES_SQL + ')', (now.isoformat(),)).fetchone()
        result['shares'] = {'active': share_metrics[0], 'views': share_metrics[1]}
        products = db.execute('SELECT COUNT(*), COALESCE(SUM(enabled=1),0) FROM products').fetchone()
        result['catalog'] = [{'view': 'products', 'label': '设备', 'total': products[0], 'enabled': products[1]}]
        for kind, label, view in [('optional', '配置', 'config-catalog'), ('tools', '工具', 'tool-catalog'), ('accessories', '附件', 'accessory-catalog')]:
            row = db.execute("""SELECT COUNT(*), COALESCE(SUM(o.enabled=1 AND c.enabled=1),0)
                FROM options o JOIN categories c ON c.id=o.category_id
                WHERE o.deleted_at IS NULL AND c.catalog_type=?""", (kind,)).fetchone()
            result['catalog'].append({'view': view, 'label': label, 'total': row[0], 'enabled': row[1]})
        if admin:
            accounts = db.execute("""SELECT COALESCE(SUM(role='customer'),0), COALESCE(SUM(role IN ('sales','admin')),0)
                FROM users WHERE deleted_at IS NULL""").fetchone()
            audits = db.execute("""SELECT a.id, a.action, a.entity_type, a.entity_id, a.created_at,
                COALESCE(NULLIF(u.display_name,''),u.email,u.phone,'已删除账号') AS actor
                FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id
                ORDER BY a.created_at DESC, a.rowid DESC LIMIT 5""").fetchall()
            result['admin'] = {'customers': accounts[0], 'staff': accounts[1], 'audits': [dict(row) for row in audits]}
        return result
