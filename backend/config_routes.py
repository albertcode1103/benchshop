from typing import Any, Dict
from fastapi.responses import Response

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from .auth_routes import current_user
from .config_repository import (
    build_snapshot,
    create_share,
    delete_saved_config,
    get_saved_config,
    get_share,
    list_saved_configs,
    list_shares,
    save_config,
)
from .rate_limit import enforce
from .quote_repository import save_quote, list_quotes, get_quote, delete_quote, list_reference_prices
from .pdf_service import configuration_pdf, quote_pdf as render_quote_pdf


router = APIRouter(prefix="/api/v1", tags=["configurations"])


class SaveConfigRequest(BaseModel):
    name: str = ""
    product_id: str
    color: str
    selections: Dict[str, Any]
    lang: str = "zh"

class QuoteRequest(BaseModel):
    config_id: str
    title: str = "配置报价单"
    items: list = []
    total_price: int = 0
    quote_id: str = None
    currency: str = "CNY"


def registered_user(user=Depends(current_user)):
    if user["role"] == "guest":
        raise HTTPException(status_code=403, detail="Login required to save or share configurations")
    return user


def staff_user(user=Depends(registered_user)):
    if user["role"] not in ("sales", "admin"):
        raise HTTPException(status_code=403, detail="Sales or admin access required")
    return user


@router.get("/configs")
def configs(user=Depends(registered_user)):
    return {"items": list_saved_configs(user["id"])}


@router.post("/configs", status_code=status.HTTP_201_CREATED)
def add_config(payload: SaveConfigRequest, user=Depends(registered_user)):
    try:
        snapshot = build_snapshot(payload.product_id, payload.color, payload.selections, payload.lang)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return save_config(user["id"], payload.name, payload.product_id, snapshot)


@router.post("/configs/pdf")
def current_config_pdf(payload: SaveConfigRequest, user=Depends(current_user)):
    try:
        snapshot = build_snapshot(payload.product_id, payload.color, payload.selections, payload.lang)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    title = payload.name.strip() or ("Configuration List" if payload.lang == "en" else "设备配置清单")
    return _pdf_response(configuration_pdf(snapshot, title), "configuration-current.pdf")


@router.get("/configs/{config_id}")
def config(config_id: str, user=Depends(registered_user)):
    result = get_saved_config(config_id, user["id"])
    if result is None:
        raise HTTPException(status_code=404, detail="Saved configuration not found")
    return result


@router.get("/configs/{config_id}/pdf")
def saved_config_pdf(config_id: str, user=Depends(registered_user)):
    result = get_saved_config(config_id, user["id"])
    if result is None:
        raise HTTPException(status_code=404, detail="Saved configuration not found")
    content = configuration_pdf(result["snapshot"], result["name"], "配置编号 / Config: {}".format(config_id[:8]))
    return _pdf_response(content, "configuration-{}.pdf".format(config_id[:8]))


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_config(config_id: str, user=Depends(registered_user)):
    if not delete_saved_config(config_id, user["id"]):
        raise HTTPException(status_code=404, detail="Saved configuration not found")
    return None


@router.post("/configs/{config_id}/share", status_code=status.HTTP_201_CREATED)
def share_config(config_id: str, user=Depends(registered_user)):
    try:
        return create_share(config_id, user["id"])
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.get("/staff/shares")
def staff_shares(user=Depends(staff_user)):
    return {"items": list_shares()}

@router.get("/quotes")
def quotes(user=Depends(staff_user)):
    return {"items": list_quotes(None if user["role"] == "admin" else user["id"])}

@router.get("/staff/reference-prices")
def reference_prices(user=Depends(staff_user)):
    return list_reference_prices()

@router.post("/quotes", status_code=status.HTTP_201_CREATED)
def add_quote(payload: QuoteRequest, user=Depends(staff_user)):
    if payload.total_price < 0 or any(float(item.get("price", 0)) < 0 for item in payload.items if isinstance(item, dict)):
        raise HTTPException(status_code=422, detail="Quote prices cannot be negative")
    try:
        if payload.currency not in ("CNY", "USD"): raise HTTPException(status_code=422, detail="Unsupported currency")
        return save_quote(payload.config_id, user["id"], payload.title, payload.items, payload.total_price, payload.quote_id, payload.currency)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

@router.get("/quotes/{quote_id}")
def quote(quote_id: str, user=Depends(staff_user)):
    result = get_quote(quote_id, None if user["role"] == "admin" else user["id"])
    if result is None: raise HTTPException(status_code=404, detail="Quote not found")
    return result

@router.get("/quotes/{quote_id}/pdf")
def quote_pdf(quote_id: str, user=Depends(staff_user)):
    result = get_quote(quote_id, None if user["role"] == "admin" else user["id"])
    if result is None: raise HTTPException(status_code=404, detail="Quote not found")
    return _pdf_response(render_quote_pdf(result), "quote-{}.pdf".format(quote_id[:8]))

@router.delete("/quotes/{quote_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_quote(quote_id: str, user=Depends(staff_user)):
    if not delete_quote(quote_id, None if user["role"] == "admin" else user["id"]):
        raise HTTPException(status_code=404, detail="Quote not found")
    return None


@router.get("/shares/{code}")
def shared_config(code: str, request: Request, user=Depends(registered_user)):
    if user["role"] not in ("sales", "admin"):
        raise HTTPException(status_code=403, detail="Sales or admin access required")
    if len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=422, detail="Share code must contain 6 digits")
    client = request.client.host if request.client else "unknown"
    enforce("share:{}:{}".format(client, code), limit=30, window_seconds=60)
    result = get_share(code)
    if result is None:
        raise HTTPException(status_code=404, detail="Share code not found or expired")
    return result


@router.get("/shares/{code}/pdf")
def shared_config_pdf(code: str, request: Request, user=Depends(staff_user)):
    result = shared_config(code, request, user)
    title = result.get("name") or "客户配置清单"
    content = configuration_pdf(result["snapshot"], title, "分享码 / Share: {}".format(code))
    return _pdf_response(content, "shared-configuration-{}.pdf".format(code))


def _pdf_response(content: bytes, filename: str) -> Response:
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="{}"'.format(filename)})
