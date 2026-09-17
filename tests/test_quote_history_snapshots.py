"""History snapshots and access checks against a disposable migrated database."""
import pytest
from fastapi.testclient import TestClient
from backend import config, database, database_upgrade
from backend.auth_routes import current_user
from backend.main import app
from backend.quote_repository import (
    save_quote, quote_history, get_quote_revision, get_quote, deliver_quote,
    get_customer_quote, archive_quote,
)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    for module in (config, database, database_upgrade):
        monkeypatch.setattr(module, "DATABASE_PATH", tmp_path / "test.db")
    database_upgrade.upgrade_database()
    with database.get_connection() as db:
        for identity, role in [("a", "sales"), ("b", "sales"), ("admin", "admin"), ("customer", "customer")]:
            db.execute("INSERT INTO users(id,role,display_name,email) VALUES (?,?,?,?)",
                       (identity, role, identity, identity + "@example.invalid"))
    yield TestClient(app)
    app.dependency_overrides.pop(current_user, None)


def save(title="First", **kwargs):
    return save_quote(None, "a", title, [{"kind": "tool", "name": title, "quantity": 2, "price": 20}], 40, **kwargs)


def test_save_apply_conflict_and_delivery_immutability(isolated):
    first = save()
    second = save("Second", quote_id=first["id"], expected_version=first["version"])
    history = quote_history(first["id"], "a")
    assert [r["event"] for r in history["revisions"]] == ["saved", "created"]
    original = get_quote_revision(history["revisions"][-1]["id"])
    assert original["title"] == "First"
    deliver_quote(first["id"], "a", recipient_user_id="customer", expected_version=second["version"])
    current = get_quote(first["id"])
    applied = save(original["title"], quote_id=first["id"], expected_version=current["version"])
    assert applied["version"] > current["version"]
    assert get_customer_quote(first["id"], "customer")["title"] == "Second"
    assert get_quote_revision(history["revisions"][-1]["id"])["title"] == "First"
    count = len(quote_history(first["id"])["revisions"])
    with pytest.raises(ValueError, match="version conflict"):
        save("Stale", quote_id=first["id"], expected_version=current["version"])
    assert len(quote_history(first["id"])["revisions"]) == count


def test_history_permissions_cross_quote_and_archived_preview(isolated):
    first, other = save(), save("Other")
    revision = quote_history(first["id"])["revisions"][0]["id"]
    url = f"/api/v1/staff/quotes/{first['id']}/history/{revision}"
    for identity, role, expected in [("a", "sales", 200), ("b", "sales", 404), ("admin", "admin", 200), ("customer", "customer", 403)]:
        app.dependency_overrides[current_user] = lambda identity=identity, role=role: {"id": identity, "role": role}
        assert isolated.get(url).status_code == expected
    app.dependency_overrides[current_user] = lambda: {"id": "a", "role": "sales"}
    assert isolated.get(f"/api/v1/staff/quotes/{other['id']}/history/{revision}").status_code == 404
    archive_quote(first["id"], "a", user_id="a", expected_version=first["version"])
    result = isolated.get(url)
    assert result.status_code == 200 and result.json()["can_apply"] is False


def test_preexisting_quote_is_captured_before_first_edit(isolated):
    first = save()
    with database.get_connection() as db:
        db.execute("DELETE FROM quote_revisions WHERE quote_id = ?", (first["id"],))
    save("Changed", quote_id=first["id"], expected_version=first["version"])
    rows = quote_history(first["id"])["revisions"]
    assert [row["event"] for row in rows] == ["saved", "baseline"]
    assert get_quote_revision(rows[-1]["id"])["title"] == "First"
