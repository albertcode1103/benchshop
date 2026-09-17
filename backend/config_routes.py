from typing import Annotated, Any, Dict, List, Optional
from fastapi.responses import Response

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator, field_validator
from .payload_bounds import validate_tree
from .pdf_identity import pdf_identity

from .auth_routes import current_user
from .personal_business import set_visibility, set_owner_share_status, hidden_ids
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
    QUOTE_ITEM_FIELDS,
    save_quote, list_quotes, get_quote, delete_quote, list_reference_prices,
    deliver_quote, withdraw_quote_delivery, list_customer_quotes, get_customer_quote,
    archive_quote, restore_quote, quote_history, get_quote_revision,
    find_active_quote_for_source, quote_source_summaries,
)
from .pdf_service import commerce_bundle_pdf, configuration_bundle_pdf, configuration_pdf, quote_pdf as render_quote_pdf, temporary_configuration_code
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
    share_lookup_status,
)
from .customer_payload import without_prices
from .user_repository import list_users, get_user_by_id
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


class CommerceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    @model_validator(mode="before")
    @classmethod
    def bounded_payload(cls, value):
        return validate_tree(value)


class SaveConfigRequest(CommerceRequest):
    name: str = ""
    product_id: str
    color: str
    selections: Dict[str, Any]
    lang: str = "zh"


class UpdateConfigRequest(SaveConfigRequest):
    version: int


class ConfigBatchRequest(CommerceRequest):
    config_ids: List[str]
    lang: str = "zh"


class CartItemRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_type: str = Field(max_length=30)
    id: str = Field(min_length=1, max_length=100)


class CartBatchRequest(CommerceRequest):
    reuse_existing: bool = False
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=80)
    items: List[CartItemRef] = Field(default_factory=list)
    lang: str = Field(default="zh", max_length=5)
    note: str = Field(default="", max_length=30)

class QuoteDeviceSpecification(BaseModel):
    model_config = ConfigDict(extra='forbid')
    key: str = Field(default='', max_length=100)
    label: str = Field(default='', max_length=1000)
    value: str = Field(default='', max_length=10000)


_quote_specifications = TypeAdapter(Annotated[List[QuoteDeviceSpecification], Field(max_length=1000)])
_quote_availability_details = TypeAdapter(Annotated[List[Annotated[str, Field(max_length=1000)]], Field(max_length=1000)])


class QuoteRequest(CommerceRequest):
    config_id: Optional[str] = Field(default=None, max_length=100)
    title: str = Field(default="配置报价单", max_length=200)
    items: List[Dict[str, Any]] = Field(default_factory=list, max_length=1000)
    total_price: float = Field(default=0.0, allow_inf_nan=False)
    quote_id: Optional[str] = Field(default=None, max_length=100)
    currency: str = "CNY"
    source_share_id: Optional[str] = Field(default=None, max_length=100)
    source_inquiry_id: Optional[str] = Field(default=None, max_length=100)
    source_type: Optional[str] = Field(default=None, pattern="^(direct|share|inquiry)$")
    source_document_version: Optional[int] = Field(default=None, ge=1)
    source_document_id: Optional[str] = Field(default=None, max_length=100)
    source_code: Optional[str] = Field(default=None, max_length=100)
    customer_name: str = Field(default="", max_length=200)
    customer_email: str = Field(default="", max_length=200)
    customer_phone: str = Field(default="", max_length=80)
    customer_address: str = Field(default="", max_length=500)
    language: str = "zh"
    version: Optional[int] = Field(default=None, ge=1)

    @field_validator('items')
    @classmethod
    def known_item_fields(cls, items):
        for item in items:
            if set(item) - QUOTE_ITEM_FIELDS:
                raise ValueError('报价项目包含不支持的字段')
            if 'device_specifications' in item:
                _quote_specifications.validate_python(item['device_specifications'])
            if 'availability_details' in item:
                _quote_availability_details.validate_python(item['availability_details'])
        return items


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
    version: Optional[int] = Field(default=None, ge=1)
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=80)


class QuoteLifecycleRequest(BaseModel):
    version: int = Field(ge=1)


class CurrentDeviceInquiryRequest(CommerceRequest):
    product_id: str = Field(min_length=1, max_length=100)
    color: str = Field(min_length=1, max_length=100)
    selections: Dict[str, Any] = Field(default_factory=dict)
    lang: str = Field(default="zh", max_length=5)
    message: str = Field(default="", max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=80)


class CartInquiryRequest(CommerceRequest):
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
    # Kept optional for older admin bundles.  Source uniqueness supplies the
    # authoritative replay guard even when a legacy client sends no key.
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=80)


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
        from .catalog_cart_repository import list_public_catalog_categories
        return without_prices({"items": list_public_catalog_items(catalog_type, lang), "categories": list_public_catalog_categories(catalog_type, lang)})
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
        result = create_commerce_share(_cart_refs(payload), user["id"], payload.lang, payload.note.strip(), payload.idempotency_key, payload.reuse_existing)
    except CatalogValidationError as error:
        raise _catalog_cart_error(error)
    except RuntimeError:
        raise AccountError("SHARE_CREATION_FAILED", status_code=503)
    write_audit(user["id"], "commerce_share_reuse" if result.get("reused") else "commerce_share_create", "config_shares" if result.get("document_version") == 1 else "commerce_shares", result["id"], {"item_count": result["item_count"]})
    return result


@router.post("/cart/export/pdf")
def export_cart_pdf(payload: CartBatchRequest, user=Depends(registered_user)):
    try:
        entries = load_cart_documents(_cart_refs(payload), user["id"], payload.lang)
        content = commerce_bundle_pdf(
            entries, user, "en" if payload.lang == "en" else "zh",
            document_code=temporary_configuration_code(),
        )
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
    status_code = 409 if code in (
        "INQUIRY_DUPLICATE_REQUEST", "INQUIRY_STATUS_CONFLICT", "INQUIRY_STATUS_TRANSITION_INVALID",
        "INQUIRY_ALREADY_CANCELLED", "INQUIRY_QUOTE_ALREADY_EXISTS", "INQUIRY_PRODUCT_INACTIVE",
        "INQUIRY_COLOR_UNAVAILABLE", "INQUIRY_OPTION_UNAVAILABLE", "INQUIRY_CART_ITEM_UNAVAILABLE",
    ) else 404 if code in ("INQUIRY_NOT_FOUND", "INQUIRY_PRODUCT_NOT_FOUND") else 403 if code == "INQUIRY_ACCESS_DENIED" else 422
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
def customer_own_inquiries(page: int = 1, page_size: int = 20, query: str = Query(default="", max_length=200), status: str = "", hidden: bool = False, user=Depends(registered_user)):
    return without_prices(list_customer_inquiries(user["id"], page, page_size, query.strip(), status, hidden))


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


@router.get("/staff/dashboard")
def staff_dashboard(days: int = 30, user=Depends(staff_user)):
    if days not in (7, 30):
        raise HTTPException(status_code=422, detail="days must be 7 or 30")
    from .dashboard_repository import dashboard
    return dashboard(user, days)


@router.get("/staff/inquiries")
def staff_inquiries(
    page: int = 1,
    page_size: int = 20,
    query: str = "",
    status: str = "all",
    lang: str = "zh",
    queue: str = Query("all", pattern="^(all|followup|stale)$"),
    user=Depends(staff_user),
):
    try:
        result = list_staff_inquiries(user["id"], user["role"], page, page_size, query, status, lang, queue)
        summaries = quote_source_summaries("inquiry", [item["id"] for item in result["items"]], user["id"])
        for item in result["items"]:
            summary = summaries.get(item["id"], {})
            if user["role"] != "admin":
                summary["quote_links"] = [link for link in summary.get("quote_links") or [] if link.get("own")]
            item.update(summary)
        return result
    except InquiryError as error:
        _raise_inquiry_error(error)


@router.get("/staff/inquiries/{inquiry_id}")
def staff_inquiry(inquiry_id: str, lang: str = "zh", user=Depends(staff_user)):
    result = get_staff_inquiry(inquiry_id, user["id"], user["role"], lang)
    if result is None:
        raise AccountError("INQUIRY_NOT_FOUND", status_code=404)
    summary = quote_source_summaries("inquiry", [inquiry_id], user["id"]).get(inquiry_id, {})
    if user["role"] != "admin":
        summary["quote_links"] = [link for link in summary.get("quote_links") or [] if link.get("own")]
    result.update(summary)
    return result


@router.get("/staff/inquiries/{inquiry_id}/pdf")
def staff_inquiry_pdf(inquiry_id: str, lang: str = "zh", user=Depends(staff_user)):
    language = "en" if lang == "en" else "zh"
    result = get_staff_inquiry(inquiry_id, user["id"], user["role"], language)
    if result is None:
        raise AccountError("INQUIRY_NOT_FOUND", status_code=404)
    entries = [
        {
            "item_type": item.get("item_type", "device_config"),
            "source_id": item.get("source_id"),
            "quantity": item.get("quantity", 1),
            "display_name": item.get("display_name", ""),
            "snapshot": item.get("snapshot") or {},
        }
        for item in result.get("items") or []
    ]
    customer = {
        "display_name": result.get("customer_name_snapshot") or result.get("customer_display_name") or "",
        "email": result.get("customer_email_snapshot") or result.get("customer_email_current") or "",
        "phone": result.get("customer_phone_snapshot") or result.get("customer_phone_current") or "",
    }
    status_labels = {
        "zh": {"new": "新询价", "assigned": "已分配", "contacted": "已联系", "quoted": "已转报价", "closed": "已完成", "cancelled": "客户已取消"},
        "en": {"new": "New", "assigned": "Assigned", "contacted": "Contacted", "quoted": "Quoted", "closed": "Closed", "cancelled": "Cancelled"},
    }
    content = commerce_bundle_pdf(
        entries,
        customer,
        language,
        include_prices=False,
        document_kind="inquiry",
        document_code=pdf_identity("inquiry", result.get("inquiry_number")),
        note=result.get("message") or "",
        status=status_labels[language].get(result.get("status"), result.get("status") or ""),
        created_at=result.get("created_at") or "",
    )
    write_audit(user["id"], "inquiry_pdf_export", "customer_inquiries", inquiry_id, {"item_count": len(entries)})
    return _pdf_response(content, pdf_identity("inquiry", result.get("inquiry_number")) + ".pdf")


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
def convert_inquiry_to_quote(inquiry_id: str, payload: InquiryQuoteRequest, response: Response, user=Depends(staff_user)):
    language = "en" if payload.currency == "USD" else "zh"
    inquiry = get_staff_inquiry(inquiry_id, user["id"], user["role"], language)
    if inquiry is None:
        raise AccountError("INQUIRY_NOT_FOUND", status_code=404)
    existing = find_active_quote_for_source("inquiry", inquiry_id, user["id"])
    if existing is not None:
        inquiry["replayed"] = True
        response.status_code = status.HTTP_200_OK
        return {"inquiry": inquiry, "quote": existing, "replayed": True, "reused": True}
    try:
        items = inquiry_quote_items(inquiry, payload.currency)
        title = payload.title.strip() or ("Inquiry {}".format(inquiry["inquiry_number"]) if language == "en" else "询价 {}".format(inquiry["inquiry_number"]))
        quote = save_quote(
            None, user["id"], title, items, 0, currency=payload.currency,
            source_inquiry_id=inquiry_id,
            source_type="inquiry", source_document_version=1,
            source_document_id=inquiry_id, source_code=inquiry["inquiry_number"],
            customer_name=inquiry.get("customer_name_snapshot") or inquiry.get("customer_display_name") or "",
            customer_email=inquiry.get("customer_email_snapshot") or "",
            customer_phone=inquiry.get("customer_phone_snapshot") or inquiry.get("customer_phone_current") or "",
            customer_address=inquiry.get("customer_address_current") or "",
            language=language, allow_any_owner=user["role"] == "admin",
        )
        result = mark_inquiry_quoted(inquiry_id, user["id"], user["role"], quote["id"], payload.version)
    except InquiryError as error:
        _raise_inquiry_error(error)
    except ValueError as error:
        if str(error) == "Quote source already exists":
            existing = find_active_quote_for_source("inquiry", inquiry_id, user["id"])
            if existing is not None:
                response.status_code = status.HTTP_200_OK
                return {"inquiry": inquiry, "quote": existing, "replayed": True, "reused": True}
        raise AccountError("INQUIRY_SNAPSHOT_INVALID", status_code=422)
    if result is None:
        raise AccountError("INQUIRY_NOT_FOUND", status_code=404)
    write_audit(user["id"], "inquiry_convert_quote", "customer_inquiries", inquiry_id, {"quote_id": quote["id"], "inquiry_number": inquiry["inquiry_number"]})
    return {"inquiry": result, "quote": quote, "replayed": False}


@router.get("/customer/me/shares")
def customer_own_shares(page: int = 1, page_size: int = 20, query: str = Query(default="", max_length=200), status: str = "", hidden: bool = False, user=Depends(registered_user)):
    from .share_quota import share_quota
    from .database import get_connection
    result = list_customer_shares(user["id"], page, page_size, query.strip(), status, hidden)
    with get_connection() as db:
        result["quota"] = share_quota(db, user["id"])
    return result


class PersonalVisibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hidden: bool


class OwnerShareStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: bool
    version: int = Field(ge=1)


@router.patch("/customer/me/records/{resource_type}/{resource_id}/visibility")
def personal_record_visibility(resource_type: str, resource_id: str, payload: PersonalVisibilityRequest, user=Depends(registered_user)):
    result = set_visibility(user["id"], resource_type, resource_id, payload.hidden)
    write_audit(user["id"], "personal_record_hide" if payload.hidden else "personal_record_restore", resource_type, resource_id, {})
    return result


@router.patch("/customer/me/shares/{share_id}/status")
def own_share_status(share_id: str, payload: OwnerShareStatusRequest, user=Depends(registered_user)):
    result = set_owner_share_status(user["id"], share_id, payload.active, payload.version)
    write_audit(user["id"], "share_owner_reopen" if payload.active else "share_owner_close", "shares", share_id, {})
    return result


@router.get("/customer/me/shares/{share_id}")
def customer_own_share(share_id: str, lang: str = "zh", user=Depends(registered_user)):
    result = get_customer_share(share_id, user["id"], "en" if lang == "en" else "zh")
    if result is None:
        raise AccountError("SHARE_NOT_FOUND", status_code=404)
    return without_prices(result)


@router.get("/customer/me/quotes")
def customer_own_quotes(page: int = 1, page_size: int = 20, query: str = Query(default="", max_length=200), status: str = "", hidden: bool = False, user=Depends(registered_user)):
    items = list_customer_quotes(user["id"])
    hidden_records = hidden_ids(user["id"], "quotes")
    unread = sum(1 for item in items if item.get("unread") and item["id"] not in hidden_records)
    items = [dict(item, hidden=hidden) for item in items if (item["id"] in hidden_records) == hidden
             and query.strip().casefold() in f"{item.get('title','')} {item.get('quote_number','')}".casefold()
             and (not status or (status == "unread" and item.get("unread")) or (status == "viewed" and not item.get("unread")) or item.get("lifecycle_status") == status)]
    size = min(max(page_size, 1), 50)
    page = min(max(page, 1), max(1, (len(items) + size - 1) // size))
    return {"items": items[(page-1)*size:page*size], "total": len(items), "page": page, "page_size": size, "unread_count": unread}


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
    if result.get("lifecycle_status") == "archived":
        raise AccountError("QUOTE_ARCHIVED", status_code=409)
    return _pdf_response(render_quote_pdf(result), pdf_identity("quote", result.get("quote_number")) + ".pdf")


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
        code_by_state = {"closed": "SHARE_CLOSED", "expired": "SHARE_EXPIRED"}
        error_code = code_by_state.get(share_lookup_status(code), "SHARE_NOT_FOUND")
        raise AccountError(error_code, field="code", status_code=410 if error_code != "SHARE_NOT_FOUND" else 404)
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
        status_code = 404 if error.code == "SHARE_NOT_FOUND" else 410 if error.code in ("SHARE_EXPIRED", "SHARE_CLOSED") else 409 if error.code == "SHARE_NO_AVAILABLE_ITEMS" else 422
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
    return _pdf_response(
        configuration_pdf(
            snapshot,
            customer=user or {},
            lang="en" if payload.lang == "en" else "zh",
            document_code=temporary_configuration_code(),
        ),
        "configuration-current.pdf",
    )


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
        content = configuration_bundle_pdf(
            configs, user, "en" if payload.lang == "en" else "zh",
            document_code=temporary_configuration_code(),
        )
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
    content = configuration_pdf(
        result["snapshot"],
        customer=user,
        lang=selected_lang,
        document_code=temporary_configuration_code(),
    )
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
    result = search_all_shares(page, page_size, query, status, product_id, created_from, created_to)
    summaries = quote_source_summaries("share", [item["id"] for item in result["items"]], user["id"])
    for item in result["items"]:
        item.update(summaries.get(item["id"], {}))
    return result


@router.get("/staff/shares/{code}/preview")
def preview_share(code: str, lang: str = "zh", user=Depends(staff_user)):
    result = get_any_share(code, "en" if lang == "en" else "zh", increment_view=False)
    if result is None:
        raise HTTPException(status_code=404, detail="Share code not found or expired")
    result.update(quote_source_summaries("share", [result["id"]], user["id"]).get(result["id"], {}))
    return result

@router.get("/quotes")
def quotes(
    status_filter: str = Query("all", alias="status", pattern="^(all|draft|sent|archived)$"),
    query: str = Query("", max_length=200),
    include_archived: bool = True,
    due: bool = False,
    user=Depends(staff_user),
):
    return {
        "items": list_quotes(
            None if user["role"] == "admin" else user["id"],
            status_filter=status_filter,
            include_archived=include_archived,
            query=query,
            due=due,
        )
    }

@router.get("/staff/reference-prices")
def reference_prices(user=Depends(staff_user)):
    return list_reference_prices()


@router.get("/staff/customers")
def staff_customers(query: str = "", customer_id: Optional[str] = None, user=Depends(staff_user)):
    items = list_users(query=query, role="customer", enabled=True, limit=50)
    if customer_id:
        customer = get_user_by_id(customer_id)
        items = [customer] if customer and customer.get("role") == "customer" and customer.get("enabled") and not customer.get("deleted_at") else []
    return {
        "items": [
            {"id": item["id"], "display_name": item.get("display_name") or "", "email": item.get("email"), "phone": item.get("phone"), "address": item.get("address") or ""}
            for item in items
        ]
    }

@router.post("/quotes", status_code=status.HTTP_201_CREATED)
def add_quote(payload: QuoteRequest, response: Response, user=Depends(staff_user)):
    try:
        source_type = payload.source_type or "direct"
        source_document_version = payload.source_document_version
        source_document_id = payload.source_document_id
        source_code = payload.source_code or ""
        source_share_id = payload.source_share_id
        source_inquiry_id = payload.source_inquiry_id
        if payload.quote_id:
            current = get_quote(payload.quote_id, None if user["role"] == "admin" else user["id"])
            if current is not None:
                source_share_id = source_share_id or current.get("source_share_id")
                source_inquiry_id = source_inquiry_id or current.get("source_inquiry_id")
                if payload.source_type is None:
                    source_type = current.get("source_type") or "direct"
                    source_document_version = current.get("source_document_version")
                    source_document_id = current.get("source_document_id")
                    source_code = current.get("source_code") or ""
        if not payload.quote_id and source_type in ("share", "inquiry") and source_document_id:
            existing = find_active_quote_for_source(source_type, source_document_id, user["id"])
            if existing is not None:
                existing["reused"] = True
                response.status_code = status.HTTP_200_OK
                return existing
        result = save_quote(
            payload.config_id, user["id"], payload.title, payload.items, payload.total_price,
            quote_id=payload.quote_id, currency=payload.currency,
            source_share_id=source_share_id, source_inquiry_id=source_inquiry_id,
            source_type=source_type, source_document_version=source_document_version,
            source_document_id=source_document_id, source_code=source_code,
            customer_name=payload.customer_name, customer_email=payload.customer_email, customer_phone=payload.customer_phone,
            customer_address=payload.customer_address,
            language=payload.language,
            allow_any_owner=user["role"] == "admin",
            expected_version=payload.version,
        )
        write_audit(user["id"], "quote_update" if payload.quote_id else "quote_create", "commerce_quotes" if result.get("document_version") == 2 else "quotes", result["id"], {"item_count": len(payload.items), "currency": payload.currency, "source_share_id": source_share_id or ""})
        return result
    except ValueError as error:
        detail = str(error)
        if detail == "Quote source already exists" and source_type in ("share", "inquiry") and source_document_id:
            existing = find_active_quote_for_source(source_type, source_document_id, user["id"])
            if existing is not None:
                existing["reused"] = True
                response.status_code = status.HTTP_200_OK
                return existing
        if detail in ("Configuration not found", "Quote not found"):
            status_code = 404
        elif detail == "Quote access denied":
            status_code = 403
        elif detail == "Quote archived":
            raise AccountError("QUOTE_ARCHIVED", status_code=409)
        elif detail == "Quote version conflict":
            raise AccountError("QUOTE_VERSION_CONFLICT", status_code=409)
        elif detail == "Quote source already exists":
            raise AccountError("QUOTE_SOURCE_ALREADY_EXISTS", status_code=409)
        else:
            status_code = 422
        raise HTTPException(status_code=status_code, detail=detail)


@router.post("/staff/quotes/{quote_id}/deliver")
def send_quote_to_customer(quote_id: str, payload: QuoteDeliveryRequest, user=Depends(staff_user)):
    owned_quote = get_quote(quote_id, None if user["role"] == "admin" else user["id"])
    if owned_quote is None:
        raise AccountError("QUOTE_NOT_FOUND", status_code=404)
    try:
        result = deliver_quote(
            quote_id, user["id"], payload.recipient_user_id, payload.source_share_id,
            expected_version=payload.version, idempotency_key=payload.idempotency_key,
        )
    except ValueError as error:
        code = {
            "Quote not found": "QUOTE_NOT_FOUND",
            "Quote recipient required": "QUOTE_RECIPIENT_REQUIRED",
            "Quote recipient unavailable": "QUOTE_RECIPIENT_UNAVAILABLE",
            "Quote archived": "QUOTE_ARCHIVED",
            "Quote version conflict": "QUOTE_VERSION_CONFLICT",
        }.get(str(error), "ACCOUNT_VALIDATION_FAILED")
        raise AccountError(code, field="recipient_user_id", status_code=404 if code == "QUOTE_NOT_FOUND" else 409 if code in ("QUOTE_ARCHIVED", "QUOTE_VERSION_CONFLICT") else 422)
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
        code = {
            "Quote not archived": "QUOTE_NOT_ARCHIVED",
            "Quote version conflict": "QUOTE_VERSION_CONFLICT",
            "Quote source already exists": "QUOTE_SOURCE_ALREADY_EXISTS",
        }.get(str(error), "ACCOUNT_VALIDATION_FAILED")
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

@router.get("/staff/quotes/{quote_id}/history/{revision_id}")
def staff_quote_revision(quote_id: str, revision_id: str, user=Depends(staff_user)):
    current = get_quote(quote_id, None if user["role"] == "admin" else user["id"])
    if current is None:
        raise AccountError("QUOTE_NOT_FOUND", status_code=404)
    revision = get_quote_revision(revision_id)
    if revision is None or revision.get("id") != quote_id:
        raise AccountError("QUOTE_NOT_FOUND", status_code=404)
    return {"quote": revision, "current_version": current.get("version"),
            "can_apply": current.get("lifecycle_status") != "archived"}


@router.get("/quotes/{quote_id}")
def quote(quote_id: str, user=Depends(staff_user)):
    result = get_quote(quote_id, None if user["role"] == "admin" else user["id"])
    if result is None: raise HTTPException(status_code=404, detail="Quote not found")
    return result

@router.get("/quotes/{quote_id}/pdf")
def quote_pdf(quote_id: str, lang: Optional[str] = Query(default=None, pattern="^(zh|en)$"), user=Depends(staff_user)):
    result = get_quote(quote_id, None if user["role"] == "admin" else user["id"])
    if result is None: raise HTTPException(status_code=404, detail="Quote not found")
    if result.get("lifecycle_status") == "archived":
        raise AccountError("QUOTE_ARCHIVED", status_code=409)
    if lang:
        from .quote_export_language import localize_quote_export
        result = localize_quote_export(result, lang)
    return _pdf_response(render_quote_pdf(result), pdf_identity("quote", result.get("quote_number")) + ".pdf")

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
def shared_config_pdf(code: str, request: Request, user=Depends(registered_user), lang: str = "zh"):
    if user["role"] not in ("admin", "sales"):
        from .database import get_connection
        with get_connection() as db:
            owned = db.execute("SELECT 1 FROM commerce_shares WHERE code=? AND created_by=? UNION ALL SELECT 1 FROM config_shares WHERE code=? AND created_by=?", (code,user["id"],code,user["id"])).fetchone()
        if not owned:
            raise HTTPException(status_code=403, detail="Share owner access required")
    result = get_any_share(code, "en" if lang == "en" else "zh", increment_view=False)
    if result is None:
        raise HTTPException(status_code=404, detail="Share code not found or expired")
    title = result.get("name") or "客户配置清单"
    entries = [{"item_type": item.get("item_type", "device_config"), "source_id": item.get("source_id"), "quantity": item.get("quantity", 1), "display_name": item.get("display_name", ""), "snapshot": item["snapshot"]} for item in result.get("items", [])]
    customer = {
        "display_name": result.get("customer_name") or result.get("sender_name"),
        "email": result.get("customer_email") or result.get("sender_email"),
        "phone": result.get("customer_phone") or result.get("sender_phone"),
    }
    # A share communicates configuration content, not a commercial offer.
    # Prices are restricted to quotation documents, regardless of whether a
    # customer or a staff member initiates the share export.
    content = commerce_bundle_pdf(
        entries, customer, "en" if lang == "en" else "zh",
        include_prices=False, document_code=pdf_identity("share", code), note=result.get("note") or "", is_share=True,
        created_at=result.get("created_at") or "",
    )
    write_audit(user["id"], "share_pdf_export", "commerce_shares" if result.get("document_version") == 2 else "config_shares", result["id"], {"code": code, "item_count": len(entries)})
    return _pdf_response(content, pdf_identity("share", code) + ".pdf")


def _pdf_response(content: bytes, filename: str) -> Response:
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="{}"'.format(filename)})
