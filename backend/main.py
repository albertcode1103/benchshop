from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import cors_origin_regex, cors_origins
from .database import initialize_database
from .repository import get_product, list_products
from .admin_routes import router as admin_router
from .auth_routes import router as auth_router
from .config_routes import router as config_router
from .media_routes import admin_media_router, public_media_router
from .audit_repository import write_audit
from .user_repository import get_user_by_token


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="BOTEN Configuration API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_origin_regex=cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


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
    if should_log and response.status_code < 400:
        authorization = request.headers.get("authorization", "")
        token = authorization.split(" ", 1)[1].strip() if authorization.lower().startswith("bearer ") else ""
        user = get_user_by_token(token) if token else None
        if user and user.get("role") in ("admin", "sales"):
            parts = [part for part in path.split("/") if part]
            entity_type = parts[3] if len(parts) > 3 else "operation"
            entity_id = parts[-1] if len(parts) > 4 else ""
            try:
                write_audit(user["id"], request.method, entity_type, entity_id, {"path": path, "status": response.status_code})
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
    return {"items": list_products(lang)}


@app.get("/api/v1/products/{product_id}")
def product(product_id: str, lang: str = Query("zh")):
    result = get_product(product_id, lang)
    if result is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return result
