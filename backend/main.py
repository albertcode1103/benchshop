from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import cors_origin_regex, cors_origins
from .database import initialize_database
from .repository import get_product, list_products
from .admin_routes import router as admin_router
from .auth_routes import router as auth_router
from .config_routes import router as config_router


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

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(config_router)


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
