from pathlib import Path
import os


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
DATABASE_PATH = Path(os.getenv("BOTEN_DATABASE_PATH", str(BACKEND_DIR / "boten.db")))
UPLOAD_DIR = Path(os.getenv("BOTEN_UPLOAD_DIR", str(PROJECT_DIR / "uploads" / "catalog")))


def cors_origins():
    raw = os.getenv("BOTEN_CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080,null")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def cors_origin_regex():
    # In local development Live Server commonly uses 5500/5501 instead of 8080.
    # Production deployments should set BOTEN_CORS_ORIGINS and disable this.
    if os.getenv("BOTEN_CORS_ORIGINS"):
        return None
    return r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
