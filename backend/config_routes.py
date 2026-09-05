from typing import Any, Dict, List, Optional
from fastapi.responses import Response

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from .auth_routes import current_user
from .config_repository import (
    build_snapshot,
    archive_saved_configs,
    create_share,
    create_share_bundle,
    delete_saved_config,
    get_saved_config,
    list_saved_configs,
    save_config,
    update_saved_config,
)
from .rate_limit import enforce
from .quote_repository import (
    save_quote, list_quotes, get_quote, delete_quote, list_reference_prices,
    deliver_quote, withdraw_quote_delivery, list_customer_quotes, get_customer_quote,
    archive_quote, restore_quote, quote_history,
)
from .pdf_service import commerce_bundle_pdf, configuration_bundle_pdf, configuration_pdf, quote_pdf as render_quote_pdf
from .audit_repository import write_audit
from .account_errors import AccountError
from .catalog_refactor_repository import CatalogValidationError
from .pricing_service import calculate_product_price, list_catalog_reference_prices
from .catalog_cart_repository import (
    archive_saved_catalog_item,
    list_public_catalog_items,
    list_saved_catalog_items,
    save_catalog_item,
    set_saved_catalog_option_quantity,
    update_saved_catalog_item,
)
from .commerce_repository import (
    archive_cart_items,
    customer_share_preview,
    create_commerce_share,
    get_any_share,
    import_share_to_cart,
    get_customer_share,
    list_customer_shares,
    load_cart_documents,
    search_all_shares,
)
from .customer_payload import without_prices
from .user_repository import list_users
from .inquiry_repository import (
    InquiryError,
    cancel_customer_inquiry,
    create_cart_inquiry,
    create_current_device_inquiry,
    get_customer_inquiry,
    get_staff_inquiry,
    inquiry_quote_items,
    list_customer_inquiries,
    list_staff_inquiries,
    mark_inquiry_quoted,
    update_staff_inquiry,
)


router = APIRouter(prefix="/api/v1", tags=["configurations"])


class SaveConfigRequest(BaseModel):
    name: str = ""
    product_id: str
    color: str
    selections: Dict[str, Any]
    lang: str = "zh"


class UpdateConfigRequest(SaveConfigRequest):
    version: int


class ConfigBatchRequest(BaseModel):
    config_ids: List[str]
    lang: str = "zh"


class CartItemRef(BaseModel):
    item_type: str = Field(max_length=30)
    id: str = Field(min_length=1, max_length=100)


class CartBatchRequest(BaseModel):
    items: List[CartItemRef] = Field(default_factory=list)
    lang: str = Field(default="zh", max_length=5)

class QuoteRequest(BaseModel):
    config_id: Optional[str] = None
    title: str = "配置报价单"
    items: list = Field(default_factory=list)
    total_price: float = 0.0
    quote_id: Optional[str] = None
    currency: str = "CNY"
    source_share_id: Optional[str] = None
    customer_name: str = ""
    customer_email: str = ""
    language: str = "zh"


class PricePreviewRequest(BaseModel):
    product_id: str
    motor_option_id: Optional[str] = None
    channel_option_id: Optional[str] = None
    power_option_id: Optional[str] = None
    optional_config_ids: List[str] = Field(default_factory=list)
    currency: str = "CNY"
    lang: str = "zh"


class SaveCatalogCartItemRequest(BaseModel):
    option_id: str = Field(max_length=100)
    quantity: int = Field(default=1, ge=1, le=999)
    lang: str = Field(default="zh", max_length=5)


class UpdateCatalogCartItemRequest(BaseModel):
    version: int = Field(ge=1)
    quantity: int = Field(ge=1, le=999)
    lang: str = Field(default="zh", max_length=5)


class SetCatalogCartQuantityRequest(BaseModel):
    quantity: int = Field(ge=0, le=999)
    lang: str = Field(default="zh", max_length=5)


class ShareImportRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=80)
    lang: str = Field(default="zh", max_length=5)


class QuoteDeliveryRequest(BaseModel):
    recipient_user_id: Optional[str] = Field(default=None, max_length=100)
    source_share_id: Optional[str] = Field(default=None, max_length=100)


class QuoteLifecycleRequest(BaseModel):
    version: int = Field(ge=1)


class CurrentDeviceInquiryRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=100)
    color: str = Field(min_length=1, max_length=100)
    selections: Dict[str, Any] = Field(default_factory=dict)
    lang: str = Field(default="zh", max_length=5)
    message: str = Field(default="", max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=80)


class CartInquiryRequest(BaseModel):
    lang: str = Field(default="zh", max_length=5)
    message: str = Field(default="", max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=80)


class InquiryCancelRequest(BaseModel):
    version: int = Field(ge=1)


class StaffInquiryUpdateRequest(BaseModel):
    version: int = Field(ge=1)
    status: Optional[str] = Field(default=None, max_length=20)
    assigned_to: Optional[str] = Field(default=None, max_length=100)


class InquiryQuoteRequest(BaseModel):
    version: int = Field(ge=1)
    currency: str = Field(default="CNY", max_length=3)
    title: str = Field(default="", max_length=200)


def registered_user(user=Depends(current_user)):
    if user["role"] == "guest":
        raise HTTPException(status_code=403, detail="Login required to save or share configurations")
    return user


def staff_user(user=Depends(registered_user)):
    if user["role"] not in ("sales", "admin"):
        raise HTTPException(status_code=403, detail="Sales or admin access required")
    return user


@router.post("/pricing/preview")
def pricing_preview(payload: PricePreviewRequest, user=Depends(staff_user)):
    try:
        return calculate_product_price(
            payload.product_id,
            motor_option_id=payload.motor_option_id,
            channel_option_id=payload.channel_option_id,
            power_option_id=payload.power_option_id,
            optional_config_ids=payload.optional_config_ids,
            currency=payload.currency,
            language=payload.lang,
        )
    except CatalogValidationError as error:
        status_code = 404 if error.code in ("CATALOG_PRODUCT_NOT_FOUND", "PRICE_VARIANT_NOT_FOUND") else 422
        raise AccountError(error.code, field=error.field or None, status_code=status_code, params=error.params)


@router.get("/catalog/reference-prices")
def catalog_reference_prices(catalog_type: str = "optional", lang: str = "zh", user=Depends(staff_user)):
    try:
        return {"items": list_catalog_reference_prices(catalog_type, lang)}
    except CatalogValidationError as error:
        raise AccountError(error.code, field=error.field or None, status_code=422, params=error.params)


@router.get("/catalog/items")
def public_catalog_items(catalog_type: str = Query("tools", alias="type"), lang: str = "zh"):
    try:
        return without_prices({"items": list_public_catalog_items(catalog_type, lang)})
    except CatalogValidationError as error:
        raise AccountError(error.code, field=error.field or None, status_code=422, params=error.params)


def _catalog_cart_error(error: CatalogValidationError) -> AccountError:
    if error.code == "CATALOG_CART_ITEM_NOT_FOUND":
        status_code = 404
    elif error.code == "CATALOG_CART_VERSION_CONFLICT":
        status_code = 409
    elif error.code == "CONFIG_ACCESS_DENIED":
        status_code = 403
    else:
        status_code = 422
    return AccountError(error.code, field=error.field or None, status_code=status_code, params=error.params)


def _cart_refs(payload: CartBatchRequest) -> List[Dict[str, str]]:
    return [{"item_type": item.item_type, "id": item.id} for item in payload.items]


@router.get("/cart/catalog-items")
def catalog_cart_items(lang: str = "zh", user=Depends(registered_user)):
    return without_prices({"items": list_saved_catalog_items(user["id"], "en" if lang == "en" else "zh")})


@router.post("/cart/catalog-items", status_code=status.HTTP_201_CREATED)
def add_catalog_cart_item(payload: SaveCatalogCartItemRequest, user=Depends(registered_user)):
    try:
        result = save_catalog_item(
            user["id"],
            payload.option_id,
            payload.quantity,
            "en" if payload.lang == "en" else "zh",
        )
    except CatalogValidationError as error:
        raise _catalog_cart_error(error)
    write_audit(
        user["id"],
        "catalog_cart_item_create",
        "saved_catalog_items",
        result["id"],
        {"option_id": result["option_id"], "catalog_type": result["catalog_type"], "quantity": result["quantity"]},
    )
    return without_prices(result)


@router.put("/cart/catalog-options/{option_id}")
def set_catalog_cart_quantity(option_id: str, payload: SetCatalogCartQuantityRequest, user=Depends(registered_user)):
    try:
        result = set_saved_catalog_option_quantity(
            user["id"],
            option_id,
            payload.quantity,
            "en" if payload.lang == "en" else "zh",
        )
    except CatalogValidationError as error:
        raise _catalog_cart_error(error)
    write_audit(
        user["id"],
        "catalog_cart_option_quantity_set",
        "saved_catalog_items",
        option_id,
        {"quantity": payload.quantity},
    )
    return without_prices(result) if result is not None else Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/cart/catalog-items/{item_id}")
def edit_catalog_cart_item(item_id: str, payload: UpdateCatalogCartItemRequest, user=Depends(registered_user)):
    try:
        result = update_saved_catalog_item(
            item_id,
            user["id"],
            version=payload.version,
            quantity=payload.quantity,
            language="en" if payload.lang == "en" else "zh",
        )
    except CatalogValidationError as error:
        raise _catalog_cart_error(error)
    write_audit(
        user["id"],
        "catalog_cart_item_update",
        "saved_catalog_items",
        item_id,
        {"version": result["version"], "quantity": result["quantity"]},
    )
    return without_prices(result)


@router.delete("/cart/catalog-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_catalog_cart_item(item_id: str, version: int = Query(..., ge=1), user=Depends(registered_user)):
    try:
        archive_saved_catalog_item(item_id, user["id"], version=version)
    except CatalogValidationError as error:
        raise _catalog_cart_error(error)
    write_audit(user["id"], "catalog_cart_item_archive", "saved_catalog_items", item_id, {"version": version})
    return None


@router.post("/cart/share", status_code=status.HTTP_201_CREATED)
def share_cart(payload: CartBatchRequest, user=Depends(registered_user)):
    try:
        result = create_commerce_share(_cart_refs(payload), user["id"], payload.lang)
    except CatalogValidationError as error:
        raise _catalog_cart_error(error)
    except RuntimeError:
        raise AccountError("SHARE_CREATION_FAILED", status_code=503)
    write_audit(user["id"], "commerce_share_create", "commerce_shares", result["id"], {"item_count": result["item_count"]})
    return result


@router.post("/cart/export/pdf")
def export_cart_pdf(payload: CartBatchRequest, user=Depends(registered_user)):
    try:
        entries = load_cart_documents(_cart_refs(payload), user["id"], payload.lang)
        content = commerce_bundle_pdf(entries, user, "en" if payload.lang == "en" else "zh")
    except CatalogValidationError as error:
        raise _catalog_cart_error(error)
    except Exception:
        raise AccountError("PDF_GENERATION_FAILED", status_code=500)
    write_audit(user["id"], "commerce_pdf_export", "cart", "batch", {"item_count": len(entries)})
    return _pdf_response(content, "BOTEN-configurations.pdf")


@router.post("/cart/batch-archive")
def archive_cart(payload: CartBatchRequest, user=Depends(registered_user)):
    try:
        count = archive_cart_items(_cart_refs(payload), user["id"])
    except CatalogValidationError as error:
        raise _catalog_cart_error(error)
    return {"archived_count": count}


def _raise_inquiry_error(error: InquiryError) -> None:
    code = str(error)
    status_code = 409 if code in ("INQUIRY_DUPLICATE_REQUEST", "INQUIRY_STATUS_CONFLICT", "INQUIRY_ALREADY_CANCELLED", "INQUIRY_QUOTE_ALREADY_EXISTS") else 404 if code == "INQUIRY_NOT_FOUND" else 403 if code == "INQUIRY_ACCESS_DENIED" else 422
    raise AccountError(code if code.startswith("INQUIRY_") else "ACCOUNT_VALIDATION_FAILED", status_code=status_code)


@router.post("/customer/inquiries/current-configuration", status_code=status.HTTP_201_CREATED)
def create_current_inquiry(payload: CurrentDeviceInquiryRequest, request: Request, user=Depends(registered_user)):
    client = request.client.host if request.client else "unknown"
    enforce("customer-inquiry:{}:{}".format(client, user["id"]), limit=20, window_seconds=900)
    try:
        result = create_current_device_inquiry(
            user["id"], payload.product_id, payload.color, payload.selections,
            payload.lang, payload.message, payload.idempotency_key,
        )
    except InquiryError as error:
        _raise_inquiry_error(error)
    write_audit(user["id"], "customer_inquiry_create", "customer_inquiries", result["id"], {"source_type": "current_device", "item_count": result["item_count"], "replayed": result["replayed"]})
    return without_prices(result)


@router.post("/customer/inquiries/cart", status_code=status.HTTP_201_CREATED)
def create_cart_inquiry_request(payload: CartInquiryRequest, request: Request, user=Depends(registered_user)):
    client = request.client.host if request.client else "unknown"
    enforce("customer-inquiry:{}:{}".format(client, user["id"]), limit=20, window_seconds=900)
    try:
        result = create_cart_inquiry(user["id"], payload.lang, payload.message, payload.idempotency_key)
    except InquiryError as error:
        _raise_inquiry_error(error)
    write_audit(user["id"], "customer_inquiry_create", "customer_inquiries", result["id"], {"source_type": "cart", "item_count": result["item_count"], "replayed": result["replayed"]})
    return without_prices(result)


@router.get("/customer/me/inquiries")
def customer_own_inquiries(page: int = 1, page_size: int = 20, user=Depends(registered_user)):
    return without_prices(list_customer_inquiries(user["id"], page, page_size))


@router.get("/customer/me/inquiries/{inquiry_id}")
def customer_own_inquiry(inquiry_id: str, lang: str = "zh", user=Depends(registered_user)):
    result = get_customer_inquiry(inquiry_id, user["id"], "en" if lang == "en" else "zh")
    if result is None:
        raise AccountError("INQUIRY_NOT_FOUND", status_code=404)
    return without_prices(result)


@router.post("/customer/me/inquiries/{inquiry_id}/cancel")
def cancel_own_inquiry(inquiry_id: str, payload: InquiryCancelRequest, user=Depends(registered_user)):
    try:
        result = cancel_customer_inquiry(inquiry_id, user["id"], payload.version)
    except InquiryError as error:
        _raise_inquiry_error(error)
    if result is None:
        raise AccountError("INQUIRY_NOT_FOUND", status_code=404)
    write_audit(user["id"], "customer_inquiry_cancel", "customer_inquiries", inquiry_id, {"version": payload.version})
    return without_prices(result)


@router.get("/staff/inquiries")
def staff_inquiries(
    page: int = 1,
    page_size: int = 20,
    query: str = "",
    status: str = "all",
    lang: str = "zh",
    user=Depends(staff_user),
):
    try:
        return list_staff_inquiries(user["id"], user["role"], page, page_size, query, status, lang)
    except InquiryError as error:
        _raise_inquiry_error(error)


@router.get("/staff/inquiries/{inquiry_id}")
def staff_inquiry(inquiry_id: str, lang: str = "zh", user=Depends(staff_user)):
    result = get_staff_inquiry(inquiry_id, user["id"], user["role"], lang)
    if result is None:
        raise AccountError("INQUIRY_NOT_FOUND", status_code=404)
    return result


@router.patch("/staff/inquiries/{inquiry_id}")
def update_inquiry(inquiry_id: str, payload: StaffInquiryUpdateRequest, user=Depends(staff_user)):
    try:
        result = update_staff_inquiry(inquiry_id, user["id"], user["role"], payload.version, payload.status, payload.assigned_to)
    except InquiryError as error:
        _raise_inquiry_error(error)
    if result is None:
        raise AccountError("INQUIRY_NOT_FOUND", status_code=404)
    write_audit(user["id"], "inquiry_update", "customer_inquiries", inquiry_id, {"status": result.get("status"), "assigned_to": result.get("assigned_to") or ""})
    return result


@router.post("/staff/inquiries/{inquiry_id}/convert-to-quote", status_code=status.HTTP_201_CREATED)
def convert_inquiry_to_quote(inquiry_id: str, payload: InquiryQuoteRequest, user=Depends(staff_user)):
    language = "en" if payload.currency == "USD" else "zh"
    inquiry = get_staff_inquiry(inquiry_id, user["id"], user["role"], language)
    if inquiry is None:
        raise AccountError("INQUIRY_NOT_FOUND", status_code=404)
    if inquiry.get("converted_quote_id"):
        raise AccountError("INQUIRY_QUOTE_ALREADY_EXISTS", status_code=409)
    try:
        items = inquiry_quote_items(inquiry)
        title = payload.title.strip() or ("Inquiry {}".format(inquiry["inquiry_number"]) if language == "en" else "询价 {}".format(inquiry["inquiry_number"]))
        quote = save_quote(
            None, user["id"], title, items, 0, currency=payload.currency,
            customer_name=inquiry.get("customer_name_snapshot") or inquiry.get("customer_display_name") or "",
            customer_email=inquiry.get("customer_email_snapshot") or "",
            language=language, allow_any_owner=user["role"] == "admin",
        )
        result = mark_inquiry_quoted(inquiry_id, user["id"], user["role"], quote["id"], payload.version)
    except InquiryError as error:
        _raise_inquiry_error(error)
    except ValueError:
        raise AccountError("INQUIRY_SNAPSHOT_INVALID", status_code=422)
    if result is None:
        raise AccountError("INQUIRY_NOT_FOUND", status_code=404)
    write_audit(user["id"], "inquiry_convert_quote", "customer_inquiries", inquiry_id, {"quote_id": quote["id"], "inquiry_number": inquiry["inquiry_number"]})
    return {"inquiry": result, "quote": quote}


@router.get("/customer/me/shares")
def customer_own_shares(page: int = 1, page_size: int = 20, user=Depends(registered_user)):
    return list_customer_shares(user["id"], page, page_size)


@router.get("/customer/me/shares/{share_id}")
def customer_own_share(share_id: str, lang: str = "zh", user=Depends(registered_user)):
    result = get_customer_share(share_id, user["id"], "en" if lang == "en" else "zh")
    if result is None:
        raise AccountError("SHARE_NOT_FOUND", status_code=404)
    return without_prices(result)


@router.get("/customer/me/quotes")
def customer_own_quotes(user=Depends(registered_user)):
    items = list_customer_quotes(user["id"])
    return {"items": items, "total": len(items), "unread_count": sum(1 for item in items if item.get("unread"))}


@router.get("/customer/me/quotes/{quote_id}")
def customer_own_quote(quote_id: str, user=Depends(registered_user)):
    result = get_customer_quote(quote_id, user["id"], mark_viewed=True)
    if result is None:
        raise AccountError("QUOTE_NOT_FOUND", status_code=404)
    return result


@router.get("/customer/me/quotes/{quote_id}/pdf")
def customer_own_quote_pdf(quote_id: str, user=Depends(registered_user)):
    result = get_customer_quote(quote_id, user["id"], mark_viewed=True)
    if result is None:
        raise AccountError("QUOTE_NOT_FOUND", status_code=404)
    return _pdf_response(render_quote_pdf(result), "quote-{}.pdf".format(quote_id[:8]))


@router.get("/customer/shares/{code}")
def customer_share(code: str, request: Request, lang: str = "zh", user=Depends(registered_user)):
    if len(code) != 6 or not code.isdigit():
        raise AccountError("SHARE_CODE_INVALID", field="code")
    client = request.client.host if request.client else "unknown"
    # Limit lookup attempts per signed-in user and client, rather than per code,
    # so changing the six-digit code cannot bypass brute-force protection.
    enforce("customer-share:{}:{}".format(client, user["id"]), limit=20, window_seconds=900)
    result = customer_share_preview(code, "en" if lang == "en" else "zh")
    if result is None:
        raise AccountError("SHARE_NOT_FOUND", field="code", status_code=404)
    return without_prices(result)


@router.post("/customer/shares/{code}/import")
def import_customer_share(code: str, payload: ShareImportRequest, request: Request, user=Depends(registered_user)):
    if len(code) != 6 or not code.isdigit():
        raise AccountError("SHARE_CODE_INVALID", field="code")
    client = request.client.host if request.client else "unknown"
    enforce("customer-share-import:{}:{}".format(client, user["id"]), limit=20, window_seconds=900)
    try:
        result = import_share_to_cart(code, user["id"], payload.idempotency_key, payload.lang)
    except CatalogValidationError as error:
        status_code = 404 if error.code == "SHARE_NOT_FOUND" else 409 if error.code == "SHARE_NO_AVAILABLE_ITEMS" else 422
        raise AccountError(error.code, field=error.field or None, status_code=status_code, params=error.params)
    write_audit(
        user["id"],
        "customer_share_import",
        "share",
        code,
        {"imported_count": result["imported_count"], "skipped_count": result["skipped_count"], "replayed": result["replayed"]},
    )
    return without_prices(result)


@router.get("/configs")
def configs(lang: str = "zh", user=Depends(registered_user)):
    return without_prices({"items": list_saved_configs(user["id"], "en" if lang == "en" else "zh")})


@router.post("/configs", status_code=status.HTTP_201_CREATED)
def add_config(payload: SaveConfigRequest, user=Depends(registered_user)):
    try:
        snapshot = build_snapshot(payload.product_id, payload.color, payload.selections, payload.lang)
    except ValueError as error:
        raise AccountError("CONFIG_SELECTION_INVALID", status_code=422)
    return without_prices(save_config(user["id"], payload.name, payload.product_id, snapshot))


@router.put("/configs/{config_id}")
def replace_config(config_id: str, payload: UpdateConfigRequest, user=Depends(registered_user)):
    try:
        snapshot = build_snapshot(payload.product_id, payload.color, payload.selections, payload.lang)
    except ValueError as error:
        raise AccountError("CONFIG_SELECTION_INVALID", status_code=422)
    existing = get_saved_config(config_id, user["id"])
    if existing is None:
        raise AccountError("SAVED_CONFIG_NOT_FOUND", status_code=404)
    result = update_saved_config(config_id, user["id"], payload.name, payload.product_id, snapshot, payload.version)
    if result is None:
        raise AccountError("SAVED_CONFIG_VERSION_CONFLICT", status_code=409)
    return without_prices(result)


@router.post("/configs/pdf")
def current_config_pdf(payload: SaveConfigRequest, user=Depends(current_user)):
    try:
        snapshot = build_snapshot(payload.product_id, payload.color, payload.selections, payload.lang)
    except ValueError as error:
        raise AccountError("CONFIG_SELECTION_INVALID", status_code=422)
    title = payload.name.strip() or ("Configuration List" if payload.lang == "en" else "设备配置清单")
    return _pdf_response(configuration_pdf(snapshot, title), "configuration-current.pdf")


def _batch_configs(config_ids: List[str], user_id: str, lang: str):
    unique_ids = list(dict.fromkeys(config_ids))
    if not unique_ids:
        raise AccountError("BATCH_SELECTION_EMPTY", status_code=422)
    if len(unique_ids) > 20:
        raise AccountError("BATCH_SELECTION_LIMIT", status_code=422)
    configs = [get_saved_config(config_id, user_id, "en" if lang == "en" else "zh") for config_id in unique_ids]
    if any(config is None for config in configs):
        raise AccountError("CONFIG_ACCESS_DENIED", status_code=403)
    return configs


@router.post("/config-exports/pdf")
def merged_config_pdf(payload: ConfigBatchRequest, user=Depends(registered_user)):
    configs = _batch_configs(payload.config_ids, user["id"], payload.lang)
    try:
        content = configuration_bundle_pdf(configs, user, "en" if payload.lang == "en" else "zh")
    except Exception:
        raise AccountError("PDF_GENERATION_FAILED", status_code=500)
    write_audit(user["id"], "configuration_pdf_export", "saved_configs", "batch", {"item_count": len(configs)})
    return _pdf_response(content, "BOTEN-configurations.pdf")


@router.post("/configs/batch-archive")
def archive_configs(payload: ConfigBatchRequest, user=Depends(registered_user)):
    _batch_configs(payload.config_ids, user["id"], payload.lang)
    try:
        count = archive_saved_configs(payload.config_ids, user["id"])
    except ValueError:
        raise AccountError("CONFIG_ACCESS_DENIED", status_code=403)
    return {"archived_count": count}


@router.post("/config-shares", status_code=status.HTTP_201_CREATED)
def share_configs(payload: ConfigBatchRequest, user=Depends(registered_user)):
    try:
        result = create_share_bundle(payload.config_ids, user["id"], payload.lang)
        write_audit(user["id"], "share_create", "config_shares", result["id"], {"item_count": result["item_count"]})
        return result
    except ValueError as error:
        code = str(error) if str(error) in ("BATCH_SELECTION_EMPTY", "BATCH_SELECTION_LIMIT", "CONFIG_ACCESS_DENIED") else "SHARE_CREATION_FAILED"
        raise AccountError(code, status_code=403 if code == "CONFIG_ACCESS_DENIED" else 422)
    except RuntimeError:
        raise AccountError("SHARE_CREATION_FAILED", status_code=503)


@router.get("/configs/{config_id}")
def config(config_id: str, lang: str = "zh", user=Depends(registered_user)):
    result = get_saved_config(config_id, user["id"], "en" if lang == "en" else "zh")
    if result is None:
        raise AccountError("SAVED_CONFIG_NOT_FOUND", status_code=404)
    return without_prices(result)


@router.get("/configs/{config_id}/pdf")
def saved_config_pdf(config_id: str, lang: str = "zh", user=Depends(registered_user)):
    selected_lang = "en" if lang == "en" else "zh"
    result = get_saved_config(config_id, user["id"], selected_lang)
    if result is None:
        raise AccountError("SAVED_CONFIG_NOT_FOUND", status_code=404)
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
        result = create_share(config_id, user["id"])
        write_audit(user["id"], "share_create", "config_shares", result["id"], {"item_count": 1, "legacy_endpoint": True})
        return result
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.get("/staff/shares")
def staff_shares(
    page: int = 1, page_size: int = 20, query: str = "", status: str = "all",
    product_id: str = "", created_from: str = "", created_to: str = "", user=Depends(staff_user),
):
    return search_all_shares(page, page_size, query, status, product_id, created_from, created_to)


@router.get("/staff/shares/{code}/preview")
def preview_share(code: str, lang: str = "zh", user=Depends(staff_user)):
    result = get_any_share(code, "en" if lang == "en" else "zh", increment_view=False)
    if result is None:
        raise HTTPException(status_code=404, detail="Share code not found or expired")
    return result

@router.get("/quotes")
def quotes(user=Depends(staff_user)):
    return {"items": list_quotes(None if user["role"] == "admin" else user["id"])}

@router.get("/staff/reference-prices")
def reference_prices(user=Depends(staff_user)):
    return list_reference_prices()


@router.get("/staff/customers")
def staff_customers(query: str = "", user=Depends(staff_user)):
    items = list_users(query=query, role="customer", enabled=True, limit=50)
    return {
        "items": [
            {"id": item["id"], "display_name": item.get("display_name") or "", "email": item.get("email"), "phone": item.get("phone")}
            for item in items
        ]
    }

@router.post("/quotes", status_code=status.HTTP_201_CREATED)
def add_quote(payload: QuoteRequest, user=Depends(staff_user)):
    try:
        result = save_quote(
            payload.config_id,
            user["id"],
            payload.title,
            payload.items,
            payload.total_price,
            payload.quote_id,
            payload.currency,
            payload.source_share_id,
            payload.customer_name,
            payload.customer_email,
            payload.language,
            allow_any_owner=user["role"] == "admin",
        )
        write_audit(user["id"], "quote_update" if payload.quote_id else "quote_create", "commerce_quotes" if result.get("document_version") == 2 else "quotes", result["id"], {"item_count": len(payload.items), "currency": payload.currency, "source_share_id": payload.source_share_id or ""})
        return result
    except ValueError as error:
        detail = str(error)
        if detail in ("Configuration not found", "Quote not found"):
            status_code = 404
        elif detail == "Quote access denied":
            status_code = 403
        elif detail == "Quote archived":
            raise AccountError("QUOTE_ARCHIVED", status_code=409)
        else:
            status_code = 422
        raise HTTPException(status_code=status_code, detail=detail)


@router.post("/staff/quotes/{quote_id}/deliver")
def send_quote_to_customer(quote_id: str, payload: QuoteDeliveryRequest, user=Depends(staff_user)):
    owned_quote = get_quote(quote_id, None if user["role"] == "admin" else user["id"])
    if owned_quote is None:
        raise AccountError("QUOTE_NOT_FOUND", status_code=404)
    try:
        result = deliver_quote(quote_id, user["id"], payload.recipient_user_id, payload.source_share_id)
    except ValueError as error:
        code = {
            "Quote not found": "QUOTE_NOT_FOUND",
            "Quote recipient required": "QUOTE_RECIPIENT_REQUIRED",
            "Quote recipient unavailable": "QUOTE_RECIPIENT_UNAVAILABLE",
            "Quote archived": "QUOTE_ARCHIVED",
        }.get(str(error), "ACCOUNT_VALIDATION_FAILED")
        raise AccountError(code, field="recipient_user_id", status_code=404 if code == "QUOTE_NOT_FOUND" else 422)
    write_audit(user["id"], "quote_deliver", "quote_deliveries", result["id"], {"quote_id": quote_id, "recipient_user_id": result["recipient_user_id"], "source_share_id": result.get("source_share_id") or ""})
    return result


@router.post("/staff/quotes/{quote_id}/withdraw")
def withdraw_quote_from_customer(quote_id: str, payload: QuoteDeliveryRequest, user=Depends(staff_user)):
    owned_quote = get_quote(quote_id, None if user["role"] == "admin" else user["id"])
    if owned_quote is None:
        raise AccountError("QUOTE_NOT_FOUND", status_code=404)
    count = withdraw_quote_delivery(quote_id, payload.recipient_user_id)
    if not count:
        raise AccountError("QUOTE_DELIVERY_NOT_FOUND", status_code=404)
    write_audit(user["id"], "quote_withdraw", "quote_deliveries", quote_id, {"recipient_user_id": payload.recipient_user_id or "", "delivery_count": count})
    return {"withdrawn_count": count}


@router.post("/staff/quotes/{quote_id}/archive")
def archive_staff_quote(quote_id: str, payload: QuoteLifecycleRequest, user=Depends(staff_user)):
    try:
        result = archive_quote(
            quote_id, user["id"],
            user_id=None if user["role"] == "admin" else user["id"],
            expected_version=payload.version,
        )
    except ValueError as error:
        code = {"Quote already archived": "QUOTE_ARCHIVED", "Quote version conflict": "QUOTE_VERSION_CONFLICT"}.get(str(error), "ACCOUNT_VALIDATION_FAILED")
        raise AccountError(code, status_code=409)
    if result is None:
        raise AccountError("QUOTE_NOT_FOUND", status_code=404)
    write_audit(user["id"], "quote_archive", "commerce_quotes", quote_id, {"lifecycle_status": "archived"})
    return result


@router.post("/staff/quotes/{quote_id}/restore")
def restore_staff_quote(quote_id: str, payload: QuoteLifecycleRequest, user=Depends(staff_user)):
    try:
        result = restore_quote(
            quote_id, user["id"],
            user_id=None if user["role"] == "admin" else user["id"],
            expected_version=payload.version,
        )
    except ValueError as error:
        code = {"Quote not archived": "QUOTE_NOT_ARCHIVED", "Quote version conflict": "QUOTE_VERSION_CONFLICT"}.get(str(error), "ACCOUNT_VALIDATION_FAILED")
        raise AccountError(code, status_code=409)
    if result is None:
        raise AccountError("QUOTE_NOT_FOUND", status_code=404)
    write_audit(user["id"], "quote_restore", "commerce_quotes", quote_id, {"lifecycle_status": result.get("lifecycle_status")})
    return result


@router.get("/staff/quotes/{quote_id}/history")
def staff_quote_history(quote_id: str, user=Depends(staff_user)):
    result = quote_history(quote_id, None if user["role"] == "admin" else user["id"])
    if result is None:
        raise AccountError("QUOTE_NOT_FOUND", status_code=404)
    return result

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
    try:
        deleted = delete_quote(quote_id, None if user["role"] == "admin" else user["id"])
    except ValueError as error:
        if str(error) == "Quote sent deletion forbidden":
            raise AccountError("QUOTE_DELETE_FORBIDDEN", status_code=409)
        raise
    if not deleted:
        raise AccountError("QUOTE_NOT_FOUND", status_code=404)
    write_audit(user["id"], "quote_delete", "quotes", quote_id)
    return None


@router.get("/shares/{code}")
def shared_config(code: str, request: Request, user=Depends(registered_user), lang: str = "zh"):
    if user["role"] not in ("sales", "admin"):
        raise HTTPException(status_code=403, detail="Sales or admin access required")
    if len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=422, detail="Share code must contain 6 digits")
    client = request.client.host if request.client else "unknown"
    enforce("share:{}:{}".format(client, code), limit=30, window_seconds=60)
    result = get_any_share(code, "en" if lang == "en" else "zh")
    if result is None:
        raise HTTPException(status_code=404, detail="Share code not found or expired")
    return result


@router.get("/shares/{code}/pdf")
def shared_config_pdf(code: str, request: Request, user=Depends(staff_user), lang: str = "zh"):
    result = get_any_share(code, "en" if lang == "en" else "zh", increment_view=False)
    if result is None:
        raise HTTPException(status_code=404, detail="Share code not found or expired")
    title = result.get("name") or "客户配置清单"
    entries = [{"item_type": item.get("item_type", "device_config"), "source_id": item.get("source_id"), "quantity": item.get("quantity", 1), "display_name": item.get("display_name", ""), "snapshot": item["snapshot"]} for item in result.get("items", [])]
    customer = {"display_name": result.get("customer_name") or result.get("sender_name"), "email": result.get("customer_email") or result.get("sender_email")}
    content = commerce_bundle_pdf(entries, customer, "en" if lang == "en" else "zh", "Share: {}".format(code), include_prices=True)
    write_audit(user["id"], "share_pdf_export", "commerce_shares" if result.get("document_version") == 2 else "config_shares", result["id"], {"code": code, "item_count": len(entries)})
    return _pdf_response(content, "shared-configuration-{}.pdf".format(code))


def _pdf_response(content: bytes, filename: str) -> Response:
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="{}"'.format(filename)})
