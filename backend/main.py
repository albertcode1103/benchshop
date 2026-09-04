from contextlib import asynccontextmanager
import logging
import uuid

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import cors_origin_regex, cors_origins
from .database import initialize_database
from .repository import get_product, get_public_product_snapshot, list_products
from .customer_payload import without_prices
from .admin_routes import router as admin_router
from .auth_routes import router as auth_router
from .config_routes import router as config_router
from .media_routes import admin_media_router, public_media_router
from .audit_repository import write_audit
from .user_repository import get_user_by_token
from .account_errors import AccountError


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="BOTEN Configuration API",
    version="0.1.0",
    lifespan=lifespan,
)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_origin_regex=cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def _request_language(request: Request) -> str:
    value = request.headers.get("x-ui-language") or request.headers.get("accept-language", "zh-CN")
    return "en" if value.lower().startswith("en") else "zh-CN"


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", uuid.uuid4().hex[:12])


@app.exception_handler(AccountError)
async def account_error_handler(request: Request, error: AccountError):
    message = error.message(_request_language(request))
    request_id = _request_id(request)
    response = JSONResponse(
        status_code=error.status_code,
        content={"detail": message, "error": {"code": error.code, "field": error.field, "params": error.params}, "request_id": request_id},
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Error-Code"] = error.code
    for name, value in error.headers.items():
        response.headers[name] = value
    return response


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, error: RequestValidationError):
    path = request.url.path
    if path.startswith(("/api/v1/auth/", "/api/v1/admin/users", "/api/v1/admin/catalog", "/api/v1/pricing/")) or (path.startswith("/api/v1/admin/products/") and path.endswith("/editor")):
        first = error.errors()[0] if error.errors() else {}
        location = first.get("loc") or []
        field = str(location[-1]) if location else None
        code = "ACCOUNT_VALIDATION_FAILED" if path.startswith(("/api/v1/auth/", "/api/v1/admin/users")) else "CATALOG_VALIDATION_FAILED"
        domain_error = AccountError(code, field=field)
        return await account_error_handler(request, domain_error)
    return JSONResponse(status_code=422, content={"detail": error.errors()})


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, error: Exception):
    request_id = _request_id(request)
    logger.exception("Unhandled API error request_id=%s path=%s", request_id, request.url.path)
    return await account_error_handler(request, AccountError("SERVER_UNAVAILABLE", status_code=500))


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = request.headers.get("x-request-id", "").strip()[:64] or uuid.uuid4().hex[:12]
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.middleware("http")
async def allow_local_private_network(request: Request, call_next):
    """Allow Chrome/WebView local-port requests during standalone development."""
    response = await call_next(request)
    if request.headers.get("access-control-request-private-network", "").lower() == "true":
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


@app.middleware("http")
async def audit_mutations(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    should_log = request.method in {"POST", "PUT", "PATCH", "DELETE"} and (
        path.startswith("/api/v1/admin/") or path.startswith("/api/v1/quotes")
    )
    is_account_operation = path.startswith("/api/v1/admin/users")
    should_write_generic_audit = (not is_account_operation and response.status_code < 400) or (is_account_operation and response.status_code >= 400)
    if should_log and should_write_generic_audit:
        user = getattr(request.state, "current_user", None)
        if user is None:
            authorization = request.headers.get("authorization", "")
            token = authorization.split(" ", 1)[1].strip() if authorization.lower().startswith("bearer ") else ""
            user = get_user_by_token(token) if token else None
        if user and user.get("role") in ("admin", "sales"):
            parts = [part for part in path.split("/") if part]
            entity_type = parts[3] if len(parts) > 3 else "operation"
            entity_id = parts[4] if entity_type == "users" and len(parts) > 4 else (parts[-1] if len(parts) > 4 else "")
            try:
                details = {"path": path, "status": response.status_code, "request_id": _request_id(request)}
                error_code = response.headers.get("X-Error-Code")
                if error_code:
                    details["error_code"] = error_code
                write_audit(user["id"], request.method if response.status_code < 400 else request.method + "_failed", entity_type, entity_id, details)
            except Exception:
                pass
    return response

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(config_router)
app.include_router(admin_media_router)
app.include_router(public_media_router)


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/products")
def products(lang: str = Query("zh")):
    return without_prices({"items": list_products(lang)})


@app.get("/api/v1/products/{product_id}")
def product(product_id: str, lang: str = Query("zh")):
    result = get_product(product_id, lang)
    if result is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return without_prices(result)


@app.get("/api/v1/products/{product_id}/snapshot")
def product_snapshot(product_id: str, lang: str = Query("zh")):
    result = get_public_product_snapshot(product_id, lang)
    if result is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return without_prices(result)
