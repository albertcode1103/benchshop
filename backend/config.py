from pathlib import Path
import os
from urllib.parse import urlsplit


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
DATABASE_PATH = Path(os.getenv("BOTEN_DATABASE_PATH", str(BACKEND_DIR / "boten.db")))
UPLOAD_DIR = Path(os.getenv("BOTEN_UPLOAD_DIR", str(PROJECT_DIR / "uploads" / "catalog")))


def cors_origins():
    raw = os.getenv("BOTEN_CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080,null")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if os.getenv("BOTEN_ENV", "development").lower() == "production":
        if not os.getenv("BOTEN_CORS_ORIGINS") or not origins:
            raise ValueError("Production requires explicit BOTEN_CORS_ORIGINS")
        for origin in origins:
            parsed = urlsplit(origin)
            if (parsed.scheme not in ("http", "https") or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or parsed.path or parsed.query or parsed.fragment
                    or "*" in origin or parsed.hostname == "example.com"
                    or parsed.hostname.endswith(".example.com")):
                raise ValueError("Production CORS must contain explicit non-placeholder origins")
            # Force validation of malformed port numbers as well.
            parsed.port
    return origins


def cors_origin_regex():
    # In local development Live Server commonly uses 5500/5501 instead of 8080.
    # Production deployments should set BOTEN_CORS_ORIGINS and disable this.
    if os.getenv("BOTEN_CORS_ORIGINS"):
        return None
    return r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
