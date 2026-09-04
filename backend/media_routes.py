import re
import uuid
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

from .auth_routes import require_catalog_manager
from .config import UPLOAD_DIR


MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_DIMENSION = 20000
MAX_IMAGE_PIXELS = 80_000_000
MEDIA_NAME = re.compile(r"^[a-f0-9]{32}\.(?:jpg|png|webp)$")

admin_media_router = APIRouter(
    prefix="/api/v1/admin/media",
    tags=["admin-media"],
    dependencies=[Depends(require_catalog_manager)],
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


def inspect_image(content: bytes) -> Dict[str, Union[int, str]]:
    extension = image_extension(content)
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            width, height = image.size
            image_format = (image.format or "").lower()
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise ValueError("The uploaded file is not a valid image") from error
    expected_format = "jpeg" if extension == "jpg" else extension
    if image_format != expected_format:
        raise ValueError("The image content does not match its file type")
    if width <= 0 or height <= 0 or width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise ValueError("Image dimensions are not supported")
    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError("Image contains too many pixels")
    return {"extension": extension, "width": int(width), "height": int(height)}


def store_image(content: bytes, upload_dir: Path = UPLOAD_DIR) -> str:
    if not content:
        raise ValueError("Image file is empty")
    if len(content) > MAX_IMAGE_BYTES:
        raise ValueError("Image cannot exceed 8 MB")
    metadata = inspect_image(content)
    upload_dir = upload_dir.resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = "{}.{}".format(uuid.uuid4().hex, metadata["extension"])
    destination = upload_dir / filename
    destination.write_bytes(content)
    return "/api/v1/media/{}".format(filename)


def validate_media_reference(path: Optional[str], upload_dir: Path = UPLOAD_DIR) -> bool:
    value = str(path or "").strip()
    if not value or not value.startswith("/api/v1/media/"):
        return True
    filename = value.rsplit("/", 1)[-1]
    return bool(MEDIA_NAME.fullmatch(filename) and (upload_dir.resolve() / filename).is_file())


async def _limited_request_body(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_IMAGE_BYTES:
                raise HTTPException(status_code=413, detail="Image cannot exceed 8 MB")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header")
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Image cannot exceed 8 MB")
        chunks.append(chunk)
    return b"".join(chunks)


@admin_media_router.post("", status_code=status.HTTP_201_CREATED)
async def upload_catalog_image(request: Request, filename: str = Query("image")):
    content = await _limited_request_body(request)
    try:
        metadata = inspect_image(content)
        path = store_image(content)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return {
        "path": path,
        "filename": Path(filename).name,
        "width": metadata["width"],
        "height": metadata["height"],
    }


@public_media_router.get("/{filename}")
def catalog_image(filename: str):
    if not MEDIA_NAME.fullmatch(filename):
        raise HTTPException(status_code=404, detail="Image not found")
    path = UPLOAD_DIR.resolve() / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, headers={"Cache-Control": "public, max-age=31536000, immutable"})
