"""Dashboard integration tests against a migrated, disposable SQLite database."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import config, database, database_upgrade
from backend.auth_routes import current_user
from backend.dashboard_repository import dashboard
from backend.inquiry_repository import list_staff_inquiries
from backend.main import app
from backend.quote_repository import list_quotes


NOW = datetime(2026, 9, 13, 4, tzinfo=timezone.utc)


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='benchshop-dashboard-')
        cls.addClassCleanup(cls.temp.cleanup)
        path = Path(cls.temp.name) / 'test.db'
        cls.patches = [patch.object(module, 'DATABASE_PATH', path) for module in (config, database, database_upgrade)]
        for item in cls.patches:
            item.start()
            cls.addClassCleanup(item.stop)
        database_upgrade.upgrade_database()
        with database.get_connection() as db:
            for user_id, role in [('admin', 'admin'), ('a', 'sales'), ('b', 'sales'), ('customer', 'customer')]:
                db.execute('INSERT INTO users(id,role,display_name,email) VALUES (?,?,?,?)', (user_id, role, user_id, user_id+'@example.invalid'))
            db.execute("INSERT INTO products(id,name,title_name,enabled) VALUES ('p','P','Product',1),('off','Off','Off',0)")
            db.execute("INSERT INTO saved_configs(id,user_id,name,product_id,snapshot_json) VALUES ('config','customer','Legacy share','p','{}')")
            for n in range(26):
                cls.inquiry(db, f'a{n:02}', 'a', updated='2026-09-09 04:00:00')
            cls.inquiry(db, 'b1', 'b')
            cls.inquiry(db, 'unassigned', None)
            cls.inquiry(db, 'boundary', 'a', updated='2026-09-10 04:00:00')
            cls.inquiry(db, 'pending', 'a')
            cls.inquiry(db, 'sent', 'a')
            cls.inquiry(db, 'closed', 'a', status='closed')
            cls.inquiry(db, 'cancelled', 'a', status='cancelled')
            cls.inquiry(db, 'beijing_today', 'b', created='2026-09-12T16:00:00+00:00')
            cls.inquiry(db, 'beijing_yesterday', 'b', created='2026-09-12T15:59:59+00:00')
            for quote_id, owner, status, valid, source in [
                ('draft_a', 'a', 'draft', None, 'pending'),
                ('draft_b', 'b', 'draft', None, None),
                ('sent_a', 'a', 'sent', '2026-09-14', 'sent'),
                ('sent_b', 'b', 'sent', '2026-09-14', None),
                ('exact_7d', 'a', 'sent', '2026-09-20T04:00:00Z', None),
                ('outside_7d', 'a', 'sent', '2026-09-20T04:00:01Z', None),
                ('expired', 'a', 'sent', '2026-09-13T04:00:00Z', None),
                ('today_valid', 'a', 'sent', '2026-09-13', None),
                ('yesterday_expired', 'a', 'sent', '2026-09-12', None),
                ('no_validity', 'a', 'sent', None, None),
                ('archived', 'a', 'archived', '2026-09-14', None),
            ]:
                db.execute('''INSERT INTO commerce_quotes(id,user_id,title,items_json,lifecycle_status,valid_until,
                    source_type,source_document_id,created_at,updated_at) VALUES (?,?,?,'[]',?,?,?,?,'2026-09-13 00:00:00','2026-09-13 00:00:00')''',
                    (quote_id, owner, quote_id, status, valid, 'inquiry' if source else 'direct', source))
            db.execute("INSERT INTO quotes(id,config_id,user_id,items_json,created_at) VALUES ('legacy_quote','config','a','[]','2026-09-13 00:00:00')")
            for n, (active, expires) in enumerate([(1, '2026-09-14'), (0, '2026-09-14'), (1, '2026-09-13T04:00:00Z')]):
                db.execute("INSERT INTO commerce_shares(id,code,created_by,expires_at,active,view_count,created_at) VALUES (?,?,'customer',?,?,3,'2026-09-13 00:00:00')", (f's{n}', f'10000{n}', expires, active))
            db.execute("INSERT INTO config_shares(id,config_id,code,created_by,expires_at,view_count,created_at) VALUES ('legacy','config','200000','customer','2026-09-14',2,'2026-09-13 00:00:00')")
            for kind in ('optional', 'tools', 'accessories'):
                db.execute('INSERT INTO categories(id,name,catalog_type) VALUES (?,?,?)', ('test-'+kind, kind, kind))
                for n in range(2):
                    db.execute('INSERT INTO options(id,category_id,code,name,enabled) VALUES (?,?,?,?,?)', (kind+str(n), 'test-'+kind, kind+str(n), kind, n))

    @staticmethod
    def inquiry(db, name, owner, status='assigned', updated='2026-09-13 00:00:00', created='2026-09-13 00:00:00'):
        db.execute('''INSERT INTO customer_inquiries(id,inquiry_number,created_by,source_type,status,assigned_to,
            idempotency_key,item_count,created_at,updated_at) VALUES (?,?,'customer','cart',?,?,?,1,?,?)''',
            (name, name, status if owner else 'new', owner, name, created, updated))

    def setUp(self):
        self.clocks = [patch('backend.' + module + '.utc_now', return_value=NOW) for module in ('dashboard_repository', 'inquiry_repository', 'dashboard_rules')]
        for clock in self.clocks:
            clock.start()
        self.addCleanup(lambda: [clock.stop() for clock in reversed(self.clocks)])

    def test_roles_and_paginated_queue_match(self):
        a = dashboard({'id': 'a', 'role': 'sales'})
        b = dashboard({'id': 'b', 'role': 'sales'})
        admin = dashboard({'id': 'admin', 'role': 'admin'})
        self.assertEqual(27, a['counts']['followup'])
        self.assertEqual(26, a['counts']['stale'])
        self.assertEqual(3, b['counts']['followup'])
        self.assertEqual(31, admin['counts']['followup'])
        self.assertNotIn('admin', a)
        self.assertNotIn('admin', b)
        self.assertIn('admin', admin)
        for user in ({'id': 'a', 'role': 'sales'}, {'id': 'b', 'role': 'sales'}, {'id': 'admin', 'role': 'admin'}):
            result = dashboard(user)
            for queue in ('followup', 'stale'):
                first = list_staff_inquiries(user['id'], user['role'], page_size=20, queue=queue)
                self.assertEqual(result['counts'][queue], first['total'])
                if queue == 'followup':
                    self.assertEqual([row['id'] for row in result['tasks']['inquiries']], [row['id'] for row in first['items'][:5]])
        self.assertEqual(7, len(list_staff_inquiries('a', 'sales', page=2, queue='followup')['items']))

    def test_quote_scope_lifecycle_and_expiry_boundaries(self):
        for owner, role in [('a', 'sales'), ('b', 'sales'), ('admin', 'admin')]:
            result = dashboard({'id': owner, 'role': role})
            due = list_quotes(None if role == 'admin' else owner, due=True)
            self.assertEqual(result['counts']['due'], len(due))
            self.assertEqual([r['id'] for r in result['tasks']['due']], [r['id'] for r in due[:5]])
            self.assertEqual(result['counts']['drafts'], len(list_quotes(None if role == 'admin' else owner, status_filter='draft')))
        a = dashboard({'id': 'a', 'role': 'sales'})
        self.assertEqual({'today_valid', 'sent_a', 'exact_7d'}, {r['id'] for r in a['tasks']['due']})
        self.assertEqual(2, a['counts']['drafts'])  # Includes legacy document once.

    def test_time_range_public_trends_and_legacy_shares(self):
        a = dashboard({'id': 'a', 'role': 'sales'}, 7)
        b = dashboard({'id': 'b', 'role': 'sales'}, 30)
        self.assertEqual(a['trend']['inquiries'], b['trend']['inquiries'][-7:])
        self.assertEqual('2026-09-13', a['trend']['dates'][-1])
        self.assertEqual(1, a['trend']['inquiries'][-2])
        self.assertEqual([0]*5, a['trend']['inquiries'][:5])
        self.assertEqual(4, a['trend']['shares'][-1])
        self.assertEqual({'active': 2, 'views': 11}, a['shares'])
        self.assertEqual({'active', 'closed', 'expired'}, {r['status'] for r in a['recent']['shares']})
        self.assertEqual(a['counts'], dashboard({'id': 'a', 'role': 'sales'}, 30)['counts'])
        self.assertEqual(10, a['trend']['quotes'][-1])
        for item in a['catalog']:
            self.assertEqual((1, 2), (item['enabled'], item['total']))

    def test_api_auth_validation_and_read_only(self):
        client = TestClient(app)
        previous = app.dependency_overrides.copy()
        self.addCleanup(lambda: (app.dependency_overrides.clear(), app.dependency_overrides.update(previous)))
        with database.get_connection() as db:
            before = db.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0]
        for role, user_id, expected in [('customer', 'customer', 403), ('sales', 'a', 200), ('admin', 'admin', 200)]:
            app.dependency_overrides[current_user] = lambda role=role, user_id=user_id: {'id': user_id, 'role': role}
            response = client.get('/api/v1/staff/dashboard?days=7')
            self.assertEqual(expected, response.status_code, response.text)
            if expected == 200:
                self.assertEqual(7, response.json()['days'])
                self.assertEqual(role == 'admin', 'admin' in response.json())
        self.assertEqual(422, client.get('/api/v1/staff/dashboard?days=14').status_code)
        self.assertEqual(422, client.get('/api/v1/staff/inquiries?queue=invalid').status_code)
        app.dependency_overrides.pop(current_user, None)
        self.assertEqual(401, client.get('/api/v1/staff/dashboard').status_code)
        with database.get_connection() as db:
            self.assertEqual(before, db.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0])


if __name__ == '__main__':
    unittest.main()
