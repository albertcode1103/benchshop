from typing import Any, Dict
from io import BytesIO
from html import escape
from pathlib import Path
import subprocess
import tempfile
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


router = APIRouter(prefix="/api/v1", tags=["configurations"])


class SaveConfigRequest(BaseModel):
    name: str = ""
    product_id: str
    color: str
    selections: Dict[str, Any]

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
        snapshot = build_snapshot(payload.product_id, payload.color, payload.selections)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return save_config(user["id"], payload.name, payload.product_id, snapshot)


@router.get("/configs/{config_id}")
def config(config_id: str, user=Depends(registered_user)):
    result = get_saved_config(config_id, user["id"])
    if result is None:
        raise HTTPException(status_code=404, detail="Saved configuration not found")
    return result


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
    currency = result.get("currency", "CNY"); symbol = "¥" if currency == "CNY" else "$"
    rows = "".join("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}{:,.2f}</td><td>{}{:,.2f}</td></tr>".format(escape(str(i.get("code", ""))), escape(str(i.get("name", ""))), int(i.get("quantity", 1)), symbol, float(i.get("price", 0)), symbol, float(i.get("price", 0)) * int(i.get("quantity", 1))) for i in result.get("items", []))
    html = """<!doctype html><meta charset='utf-8'><style>@page{size:A4;margin:18mm}body{font-family:'Microsoft YaHei','Noto Sans CJK SC',sans-serif;color:#17202a}h1{font-size:24px}table{width:100%;border-collapse:collapse;margin-top:24px}th,td{padding:9px;border-bottom:1px solid #ddd;text-align:left}th{background:#f5f6f7}.total{text-align:right;font-size:20px;font-weight:700;margin-top:22px}</style><h1>{}</h1><p>报价编号：{}　币种：{}</p><table><thead><tr><th>编号</th><th>项目</th><th>数量</th><th>单价</th><th>小计</th></tr></thead><tbody>{}</tbody></table><div class='total'>总计：{}{:,.2f}</div>""".format(escape(result["title"]), escape(quote_id[:8]), currency, rows, symbol, float(result["total_price"]))
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    if edge.exists():
        with tempfile.TemporaryDirectory(prefix="boten-quote-") as folder:
            html_path = Path(folder) / "quote.html"; pdf_path = Path(folder) / "quote.pdf"; html_path.write_text(html, encoding="utf-8")
            subprocess.run([str(edge), "--headless", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf={}".format(pdf_path), html_path.as_uri()], check=True, timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if pdf_path.exists(): return Response(pdf_path.read_bytes(), media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="quote-{}.pdf"'.format(quote_id[:8])})
    lines = [result["title"]] + ["{} {} x{}    {:.2f}".format(i.get("code", ""), i.get("name", ""), i.get("quantity", 1), float(i.get("price", 0))) for i in result.get("items", [])] + ["Total: {:.2f} {}".format(float(result["total_price"]), currency)]
    stream = BytesIO(); objects = []
    content = "BT /F1 12 Tf 50 780 Td " + " ".join("({}) Tj 0 -20 Td".format(str(line).replace("(", "[").replace(")", "]")) for line in lines) + " ET"
    objects.append("<< /Type /Catalog /Pages 2 0 R >>"); objects.append("<< /Type /Pages /Kids [3 0 R] /Count 1 >>"); objects.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"); objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"); objects.append("<< /Length %d >>\nstream\n%s\nendstream" % (len(content.encode("latin-1", "replace")), content))
    pdf = "%PDF-1.4\n"; offsets = [0]
    for index, obj in enumerate(objects, 1): offsets.append(len(pdf.encode("latin-1"))); pdf += "{} 0 obj\n{}\nendobj\n".format(index, obj)
    start = len(pdf.encode("latin-1")); pdf += "xref\n0 {}\n0000000000 65535 f \n".format(len(objects)+1) + "".join("%010d 00000 n \n" % off for off in offsets[1:]) + "trailer\n<< /Size {} /Root 1 0 R >>\nstartxref\n{}\n%%EOF".format(len(objects)+1, start)
    return Response(pdf.encode("latin-1", "replace"), media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="quote-{}.pdf"'.format(quote_id[:8])})

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
