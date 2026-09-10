import asyncio
import json
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request
from backend.main import request_validation_error_handler
from backend.main import app
from fastapi.testclient import TestClient
import pytest


def test_value_error_context_returns_422_without_echoing_input():
    error = RequestValidationError([{"type": "value_error", "loc": ("body",),
                                    "msg": "Payload exceeds limit", "input": {"secret": "private"},
                                    "ctx": {"error": ValueError("too large")}}])
    request = Request({"type": "http", "path": "/api/v1/configs", "headers": []})
    response = asyncio.run(request_validation_error_handler(request, error))
    assert response.status_code == 422
    data = json.loads(response.body)
    assert data["detail"][0]["type"] == "value_error"
    assert "input" not in data["detail"][0]
    assert "ctx" not in data["detail"][0]


@pytest.mark.parametrize("path", ["/api/v1/configs", "/api/v1/cart/catalog-items",
                                   "/api/v1/config-shares/missing", "/api/v1/shares/missing",
                                   "/api/v1/customer/me/quotes", "/api/v1/staff/inquiries"])
def test_sensitive_error_responses_cannot_be_cached(path):
    # No lifespan: unauthenticated requests must not need a database migration.
    client = TestClient(app)
    try:
        response = client.get(path)
        assert response.status_code in (401, 403, 404, 405)
        assert response.headers["cache-control"] == "no-store"
    finally:
        client.close()
