import pytest
from backend.config import cors_origins, cors_origin_regex


@pytest.mark.parametrize("value", ["", "null", "*", "https://benchshop.example.com",
                                   "https://host/path", "https://user@host", "https://host:bad"])
def test_production_rejects_unsafe_cors(monkeypatch, value):
    monkeypatch.setenv("BOTEN_ENV", "production")
    monkeypatch.setenv("BOTEN_CORS_ORIGINS", value)
    with pytest.raises(ValueError):
        cors_origins()


def test_explicit_lan_origin_and_development(monkeypatch):
    monkeypatch.setenv("BOTEN_ENV", "production")
    monkeypatch.setenv("BOTEN_CORS_ORIGINS", "http://192.168.31.69:8080")
    assert cors_origins() == ["http://192.168.31.69:8080"]
    assert cors_origin_regex() is None
    monkeypatch.delenv("BOTEN_CORS_ORIGINS")
    monkeypatch.setenv("BOTEN_ENV", "development")
    assert "http://localhost:8080" in cors_origins()
    assert cors_origin_regex()
