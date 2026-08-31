import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from .auth_routes import require_admin
from .config import UPLOAD_DIR


MAX_IMAGE_BYTES = 8 * 1024 * 1024
MEDIA_NAME = re.compile(r"^[a-f0-9]{32}\.(?:jpg|png|webp)$")

admin_media_router = APIRouter(
    prefix="/api/v1/admin/media",
    tags=["admin-media"],
    dependencies=[Depends(require_admin)],
)
public_media_router = APIRouter(prefix="/api/v1/media", tags=["media"])


def image_extension(content: bytes) -> str:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "webp"
    raise ValueError("Only PNG, JPEG and WebP images are supported")


def store_image(content: bytes, upload_dir: Path = UPLOAD_DIR) -> str:
    if not content:
        raise ValueError("Image file is empty")
    if len(content) > MAX_IMAGE_BYTES:
        raise ValueError("Image cannot exceed 8 MB")
    extension = image_extension(content)
    upload_dir = upload_dir.resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = "{}.{}".format(uuid.uuid4().hex, extension)
    destination = upload_dir / filename
    destination.write_bytes(content)
    return "/api/v1/media/{}".format(filename)


@admin_media_router.post("", status_code=status.HTTP_201_CREATED)
async def upload_catalog_image(request: Request, filename: str = Query("image")):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_IMAGE_BYTES:
                raise HTTPException(status_code=413, detail="Image cannot exceed 8 MB")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header")
    try:
        path = store_image(await request.body())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return {"path": path, "filename": Path(filename).name}


@public_media_router.get("/{filename}")
def catalog_image(filename: str):
    if not MEDIA_NAME.fullmatch(filename):
        raise HTTPException(status_code=404, detail="Image not found")
    path = UPLOAD_DIR.resolve() / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, headers={"Cache-Control": "public, max-age=31536000, immutable"})
