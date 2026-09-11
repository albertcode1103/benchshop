"""Quota and deletion tests use a standalone database, never project data."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import pytest
from backend.account_errors import AccountError
from backend.share_quota import enforce_share_quota, share_quota
from backend import personal_business, commerce_repository


@pytest.fixture
def database(tmp_path, monkeypatch):
    path = tmp_path / "quota.db"
    @contextmanager
    def connection():
        db = sqlite3.connect(path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()
    with connection() as db:
        db.execute("CREATE TABLE users(id TEXT PRIMARY KEY,role TEXT)")
        db.executemany("INSERT INTO users VALUES(?,?)", [("c", "customer"), ("s", "sales"), ("a", "admin")])
        for table in ("commerce_shares", "config_shares"):
            db.execute(f"CREATE TABLE {table}(id TEXT PRIMARY KEY,created_by TEXT,active INTEGER,expires_at TEXT,owner_closed INTEGER DEFAULT 0,customer_version INTEGER DEFAULT 0)")
        db.execute("CREATE TABLE personal_business_visibility(user_id TEXT,resource_type TEXT,resource_id TEXT,hidden INTEGER,updated_at TEXT,UNIQUE(user_id,resource_type,resource_id))")
    monkeypatch.setattr(personal_business, "get_connection", connection)
    monkeypatch.setattr(commerce_repository, "get_connection", connection)
    return connection


def add(db, identifier, owner="c", table="commerce_shares", active=1, expiry="2999-01-01T00:00:00+00:00"):
    db.execute(f"INSERT INTO {table}(id,created_by,active,expires_at) VALUES(?,?,?,?)", (identifier, owner, active, expiry))


def test_combined_limit_expiry_and_role_exemption(database):
    with database() as db:
        for i in range(10):
            add(db, str(i), table="config_shares" if i % 2 else "commerce_shares")
        add(db, "expired", expiry="2000-01-01")
        add(db, "closed", active=0)
        assert share_quota(db, "c") == {"used": 10, "limit": 10, "remaining": 0, "limited": True}
        with pytest.raises(AccountError, match="10"):
            enforce_share_quota(db, "c")
        for owner in ("s", "a"):
            for i in range(11):
                add(db, owner + str(i), owner)
            assert enforce_share_quota(db, owner)["limit"] is None


def test_delete_closes_restore_does_not_reopen_and_admin_checks_limit(database):
    with database() as db:
        for i in range(10): add(db, str(i))
    personal_business.set_visibility("c", "shares", "0", True)
    with database() as db:
        assert share_quota(db, "c")["used"] == 9
        assert db.execute("SELECT active,owner_closed,customer_version FROM commerce_shares WHERE id='0'").fetchone()[:] == (0, 1, 1)
    with pytest.raises(Exception): commerce_repository.set_any_share_active("0", True)
    personal_business.set_visibility("c", "shares", "0", False)
    with database() as db:
        assert share_quota(db, "c")["used"] == 9
        add(db, "replacement")
    with pytest.raises(AccountError): personal_business.set_owner_share_status("c", "0", True, 1)
    with pytest.raises(AccountError): commerce_repository.set_any_share_active("0", True)
    personal_business.set_visibility("c", "shares", "replacement", True)
    assert personal_business.set_owner_share_status("c", "0", True, 1)["active"]


def test_concurrent_count_and_insert_use_one_write_transaction(database):
    with database() as db:
        for i in range(9): add(db, str(i))
    def attempt(i):
        try:
            with database() as db:
                db.execute("BEGIN IMMEDIATE")
                enforce_share_quota(db, "c")
                add(db, "race-" + str(i))
            return True
        except AccountError:
            return False
    with ThreadPoolExecutor(max_workers=5) as executor:
        assert sum(executor.map(attempt, range(5))) == 1
    with database() as db: assert share_quota(db, "c")["used"] == 10
