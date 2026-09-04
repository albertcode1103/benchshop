import sqlite3
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .auth_routes import require_admin, require_catalog_manager
from .user_repository import (
    archive_user,
    contact_conflict_field,
    count_users,
    create_user,
    get_user_by_id,
    list_users,
    restore_user,
    set_user_enabled,
    update_user,
)
from .commerce_repository import deactivate_any_share, search_all_shares, set_any_share_active
from .audit_repository import list_audit_logs, write_audit
from .admin_catalog_repository import (
    get_admin_product,
    list_admin_products,
    replace_colors,
    replace_option_mappings,
    update_product,
    list_config_categories,
    update_config_option,
    create_config_category,
    create_config_option,
    update_config_category,
    update_product_option_override,
    create_product,
    config_option_references,
    delete_config_option,
    config_category_references,
    delete_config_category,
    save_product_configuration,
)
from .excel_service import catalog_template, parse_xlsx
from .database import get_connection
from .database_maintenance import create_backup
from .account_validation import normalize_email, normalize_phone, validate_contact, validate_display_name, validate_password, validate_role
from .account_errors import AccountError
from .catalog_refactor_repository import (
    CatalogValidationError,
    create_catalog_category,
    create_catalog_item,
    delete_catalog_category_v2,
    delete_catalog_item,
    disable_catalog_item,
    get_catalog_tree,
    get_product_editor,
    save_product_editor,
    update_catalog_category_v2,
    update_catalog_item,
    reorder_catalog_items,
)
from .translation_service import translation_draft


router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_catalog_manager)])

CATALOG_SHEET_HEADERS = [
    ["设备型号", "中文名称", "英文名称", "人民币参考价", "美元参考价", "启用"],
    ["配置编号", "分类编号", "中文名称", "英文名称", "中文描述", "英文描述", "备注", "人民币价格", "美元价格", "启用"],
    ["设备型号", "电机配置编号", "人民币基础价", "美元基础价"],
    ["设备型号", "参数ID", "中文项目", "英文项目", "中文数据", "英文数据", "排序"],
]


def _enforce_catalog_request_size(request: Request, limit: int = 2 * 1024 * 1024) -> None:
    value = request.headers.get("content-length")
    if not value:
        return
    try:
        too_large = int(value) > limit
    except ValueError:
        raise AccountError("ACCOUNT_VALIDATION_FAILED", field="content_length")
    if too_large:
        raise AccountError("CATALOG_REQUEST_TOO_LARGE", field="request", status_code=413)

@router.get("/catalog-template.xlsx")
def export_catalog_template():
    with get_connection() as db:
        motor_prices = [dict(row) for row in db.execute("SELECT product_id, motor_option_id, base_price_cny, base_price_usd FROM product_motor_prices ORDER BY product_id, motor_option_id")]
        specifications = [dict(row) for row in db.execute("SELECT id, product_id, label, label_en, value, value_en, sort_order FROM product_specifications ORDER BY product_id, sort_order, id")]
    content = catalog_template(list_admin_products(), list_config_categories(), motor_prices, specifications)
    return Response(content=content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=boten-catalog-template.xlsx"})

@router.post("/catalog-template/preview")
async def preview_catalog_template(request: Request):
    data = await request.body()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Excel 文件不能超过 10MB")
    try:
        sheets = parse_xlsx(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="无法解析 Excel 文件") from exc
    report=[]
    with get_connection() as db:
        product_ids={r[0] for r in db.execute("SELECT id FROM products").fetchall()}
        option_ids={r[0] for r in db.execute("SELECT id FROM options").fetchall()}
    for index, rows in enumerate(sheets):
        headers=rows[0] if rows else []
        errors=[]
        if headers != CATALOG_SHEET_HEADERS[index]: errors.append("表头不匹配")
        for line, row in enumerate(rows[1:], 2):
            key=row[0] if row else ""
            if index in (0,3) and key not in product_ids: errors.append(f"第{line}行：未知设备型号 {key}")
            if index == 1 and key not in option_ids: errors.append(f"第{line}行：未知配置编号 {key}")
            if index == 2 and (key not in product_ids or len(row) < 2 or row[1] not in option_ids): errors.append(f"第{line}行：设备或电机编号无效")
        report.append({"rows": max(0,len(rows)-1),"headers":headers,"errors":errors[:50]})
    return {"valid": all(not item["errors"] for item in report), "sheets": report}

@router.post("/catalog-template/commit")
async def commit_catalog_template(request: Request, user=Depends(require_catalog_manager)):
    data = await request.body()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Excel 文件不能超过 10MB")
    try:
        sheets = parse_xlsx(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="无法解析 Excel 文件") from exc
    if len(sheets) != 4 or any(not sheet or sheet[0] != CATALOG_SHEET_HEADERS[index] for index, sheet in enumerate(sheets)):
        raise HTTPException(status_code=400, detail="Excel 工作表或表头不匹配，请使用最新模板")
    backup = create_backup(keep=30)
    updates=[]
    with get_connection() as db:
        for row in sheets[0][1:]:
            if len(row) < 6: continue
            try: cny=int(row[3] or 0); usd=int(row[4] or 0)
            except ValueError: raise HTTPException(status_code=400, detail=f"设备 {row[0]} 价格无效")
            if cny < 0 or usd < 0: raise HTTPException(status_code=400, detail=f"设备 {row[0]} 价格不能为负")
            if db.execute("SELECT 1 FROM products WHERE id=?", (row[0],)).fetchone() is None: raise HTTPException(status_code=400, detail=f"未知设备型号 {row[0]}")
            updates.append((row[1],row[2],cny,usd,1 if str(row[5]).lower() not in ("0","false","否") else 0,row[0]))
        db.executemany("UPDATE products SET name=?,name_en=?,base_price=?,price_usd=?,enabled=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", updates)
        option_updates=[]
        if len(sheets)>1 and sheets[1] and sheets[1][0] == ["配置编号","分类编号","中文名称","英文名称","中文描述","英文描述","备注","人民币价格","美元价格","启用"]:
            for row in sheets[1][1:]:
                if len(row)<10: continue
                try: cny=int(row[7] or 0); usd=int(row[8] or 0)
                except ValueError: raise HTTPException(status_code=400, detail=f"配置 {row[0]} 价格无效")
                if cny<0 or usd<0: raise HTTPException(status_code=400, detail=f"配置 {row[0]} 价格不能为负")
                if db.execute("SELECT 1 FROM options WHERE id=?", (row[0],)).fetchone() is None: raise HTTPException(status_code=400, detail=f"未知配置编号 {row[0]}")
                option_updates.append((row[2],row[3],row[4],row[5],row[6],cny,usd,1 if str(row[9]).lower() not in ("0","false","否") else 0,row[0]))
            db.executemany("UPDATE options SET name=?,name_en=?,description=?,description_en=?,notes=?,price=?,price_usd=?,enabled=? WHERE id=?", option_updates)
        motor_updates=[]
        if len(sheets)>2:
            for row in sheets[2][1:]:
                if len(row)<4: continue
                try: cny=int(row[2] or 0); usd=int(row[3] or 0)
                except ValueError: raise HTTPException(status_code=400, detail="电机价格无效")
                if cny<0 or usd<0: raise HTTPException(status_code=400, detail="电机价格不能为负")
                motor_updates.append((row[0],row[1],cny,usd))
            for product_id, motor_id, cny, usd in motor_updates:
                if db.execute("SELECT 1 FROM product_options WHERE product_id=? AND option_id=?", (product_id,motor_id)).fetchone() is None: raise HTTPException(status_code=400, detail="电机组合不存在")
                db.execute("INSERT INTO product_motor_prices(product_id,motor_option_id,base_price_cny,base_price_usd) VALUES(?,?,?,?) ON CONFLICT(product_id,motor_option_id) DO UPDATE SET base_price_cny=excluded.base_price_cny,base_price_usd=excluded.base_price_usd", (product_id,motor_id,cny,usd))
        specs_updated=0
        if len(sheets)>3:
            for row in sheets[3][1:]:
                if len(row)<7: continue
                if db.execute("SELECT 1 FROM products WHERE id=?", (row[0],)).fetchone() is None: raise HTTPException(status_code=400, detail=f"未知设备型号 {row[0]}")
                if row[1] and db.execute("SELECT 1 FROM product_specifications WHERE id=? AND product_id=?", (row[1],row[0])).fetchone() is not None:
                    db.execute("UPDATE product_specifications SET label=?,label_en=?,value=?,value_en=?,sort_order=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND product_id=?", (row[2],row[3],row[4],row[5],int(row[6] or 0),row[1],row[0])); specs_updated+=1
    counts = {"updated": len(updates), "options_updated": len(option_updates), "motor_prices_updated": len(motor_updates), "specifications_updated": specs_updated}
    write_audit(user["id"], "catalog_import", "catalog", "excel", {**counts, "backup": backup.name})
    return {**counts, "backup": backup.name}


class CreateStaffRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    phone_country: Optional[str] = None
    password: str
    display_name: str = ""
    role: str = "sales"


class UserStatusRequest(BaseModel):
    enabled: bool
    version: int = Field(ge=1)

class UserUpdateRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    phone_country: Optional[str] = None
    display_name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    version: int = Field(ge=1)


class UserRoleRequest(BaseModel):
    role: str
    version: int = Field(ge=1)


class UserPasswordResetRequest(BaseModel):
    password: str
    version: int = Field(ge=1)


class UserArchiveRequest(BaseModel):
    reason: str = Field(default="", max_length=500)
    version: int = Field(ge=1)


class UserRestoreRequest(BaseModel):
    version: int = Field(ge=1)


class ProductUpdateRequest(BaseModel):
    name: Optional[str] = None
    title_name: Optional[str] = None
    description: Optional[str] = None
    base_price: Optional[int] = None
    enabled: Optional[bool] = None
    sort_order: Optional[int] = None
    name_en: Optional[str] = None
    title_name_en: Optional[str] = None
    description_en: Optional[str] = None
    price_usd: Optional[int] = None

class ProductCreateRequest(BaseModel):
    id: str
    name: str
    name_en: str = ""
    title_name: str
    title_name_en: str = ""
    description: str = ""
    description_en: str = ""
    base_price: int = 0
    price_usd: int = 0


class ProductColorRequest(BaseModel):
    code: str
    label: str
    label_en: str = ""
    image_path: Optional[str] = None
    is_default: bool = False


class ProductColorEditorRequest(BaseModel):
    id: Optional[str] = Field(default=None, max_length=100)
    name_zh: str = Field(max_length=200)
    name_en: str = Field(max_length=200)
    display_color: str = Field(default="#374151", max_length=7)
    image_path: Optional[str] = Field(default=None, max_length=1000)
    image_width: Optional[int] = Field(default=None, ge=1, le=20000)
    image_height: Optional[int] = Field(default=None, ge=1, le=20000)
    is_default: bool = False
    enabled: bool = True
    sort_order: int = 0
    translation_status: str = Field(default="machine_draft", max_length=30)


class ProductColorsRequest(BaseModel):
    colors: List[ProductColorRequest]


class ProductMappingsRequest(BaseModel):
    option_ids: List[str]

class MotorBasePriceRequest(BaseModel):
    base_price_cny: int = 0
    base_price_usd: int = 0

class ProductSpecificationRequest(BaseModel):
    id: Optional[str] = None
    label: str = ""
    label_en: str = ""
    value: str = ""
    value_en: str = ""
    sort_order: int = 0


class ProductSpecificationEditorRequest(BaseModel):
    id: Optional[str] = Field(default=None, max_length=100)
    label: str = Field(default="", max_length=200)
    label_en: str = Field(default="", max_length=200)
    value: str = Field(default="", max_length=500)
    value_en: str = Field(default="", max_length=500)
    sort_order: int = 0

class ProductOptionOverrideRequest(BaseModel):
    description_override: Optional[str] = None
    description_override_en: Optional[str] = None
    price_override: Optional[int] = None


class ProductSaveRequest(ProductUpdateRequest):
    colors: List[ProductColorRequest]
    option_ids: List[str]
    option_overrides: Dict[str, ProductOptionOverrideRequest] = Field(default_factory=dict)
    motor_prices: Dict[str, MotorBasePriceRequest] = Field(default_factory=dict)
    specifications: List[ProductSpecificationRequest] = Field(default_factory=list)


class ConfigOptionUpdateRequest(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    image_path: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    price: Optional[int] = None
    enabled: Optional[bool] = None
    sort_order: Optional[int] = None
    name_en: Optional[str] = None
    description_en: Optional[str] = None
    price_usd: Optional[int] = None


class ConfigCategoryCreateRequest(BaseModel):
    name: str
    name_en: str = ""
    description: str = ""
    description_en: str = ""
    multiple: bool = True

class ConfigCategoryUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    multiple: Optional[bool] = None
    sort_order: Optional[int] = None
    name_en: Optional[str] = None
    description_en: Optional[str] = None


class ConfigOptionCreateRequest(ConfigOptionUpdateRequest):
    category_id: str
    code: str
    name: str


class CatalogCategoryCreateV2Request(BaseModel):
    parent_id: str = Field(max_length=100)
    name_zh: str = Field(max_length=200)
    name_en: str = Field(max_length=200)
    description_zh: str = Field(default="", max_length=5000)
    description_en: str = Field(default="", max_length=5000)
    enabled: bool = True
    sort_order: int = 0
    translation_status: str = Field(default="machine_draft", max_length=30)


class CatalogCategoryUpdateV2Request(CatalogCategoryCreateV2Request):
    parent_id: str = Field(default="catalog-optional", max_length=100)
    version: int = Field(ge=1)


class CatalogItemV2Request(BaseModel):
    category_id: str = Field(max_length=100)
    code: str = Field(max_length=200)
    name_zh: str = Field(max_length=300)
    name_en: str = Field(max_length=300)
    description_zh: str = Field(default="", max_length=10000)
    description_en: str = Field(default="", max_length=10000)
    note_zh: str = Field(default="", max_length=5000)
    note_en: str = Field(default="", max_length=5000)
    image_path: Optional[str] = Field(default=None, max_length=1000)
    image_width: Optional[int] = Field(default=None, ge=1, le=20000)
    image_height: Optional[int] = Field(default=None, ge=1, le=20000)
    price_cny: int = Field(default=0, ge=0)
    price_usd: int = Field(default=0, ge=0)
    enabled: bool = True
    sort_order: int = 0
    translation_status: str = Field(default="machine_draft", max_length=30)


class CatalogItemUpdateV2Request(CatalogItemV2Request):
    version: int = Field(ge=1)


class VersionedCatalogActionRequest(BaseModel):
    version: int = Field(ge=1)


class CatalogOrderItemRequest(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=1)


class CatalogOrderRequest(BaseModel):
    category_id: str = Field(min_length=1, max_length=100)
    items: List[CatalogOrderItemRequest] = Field(min_length=1, max_length=1000)


class TranslationDraftRequest(BaseModel):
    values: Dict[str, str] = Field(default_factory=dict)


class BaseOptionEditorRequest(BaseModel):
    id: Optional[str] = None
    name_zh: str
    name_en: str
    price_cny_minor: int = Field(default=0, ge=0)
    price_usd_minor: int = Field(default=0, ge=0)
    price_confirmed: bool = False
    is_free: bool = False
    sort_order: int = 0
    enabled: bool = True
    translation_status: str = "machine_draft"


class BaseOptionGroupEditorRequest(BaseModel):
    id: Optional[str] = None
    option_type: str
    required: bool = True
    sort_order: int = 0
    enabled: bool = True
    options: List[BaseOptionEditorRequest] = Field(default_factory=list)


class PriceVariantEditorRequest(BaseModel):
    id: Optional[str] = None
    motor_option_id: Optional[str] = None
    channel_option_id: Optional[str] = None
    price_cny_minor: int = Field(default=0, ge=0)
    price_usd_minor: int = Field(default=0, ge=0)
    price_confirmed: bool = False
    enabled: bool = True


class ProductEditorV2Request(BaseModel):
    version: int = Field(ge=1)
    model: str = Field(max_length=200)
    product_name_zh: str = Field(max_length=300)
    product_name_en: str = Field(max_length=300)
    overview_zh: str = Field(default="", max_length=10000)
    overview_en: str = Field(default="", max_length=10000)
    translation_status: str = Field(default="machine_draft", max_length=30)
    enabled: bool = True
    colors: List[ProductColorEditorRequest] = Field(default_factory=list, max_length=50)
    specifications: List[ProductSpecificationEditorRequest] = Field(default_factory=list, max_length=100)
    base_option_groups: List[BaseOptionGroupEditorRequest] = Field(max_length=3)
    price_variants: List[PriceVariantEditorRequest] = Field(max_length=500)
    optional_config_ids: List[str] = Field(default_factory=list, max_length=1000)
    optional_config_overrides: Dict[str, ProductOptionOverrideRequest] = Field(default_factory=dict)


def _catalog_error(error: CatalogValidationError) -> AccountError:
    if error.code in ("CATALOG_PRODUCT_NOT_FOUND", "CATALOG_CATEGORY_NOT_FOUND", "CATALOG_ITEM_NOT_FOUND"):
        status_code = 404
    elif error.code in (
        "CATALOG_VERSION_CONFLICT",
        "CATALOG_MODEL_DUPLICATE",
        "CATALOG_CATEGORY_DUPLICATE",
        "CATALOG_CATEGORY_PROTECTED",
        "CATALOG_CATEGORY_NOT_EMPTY",
        "CATALOG_CODE_DUPLICATE",
        "CATALOG_ITEM_TYPE_CHANGE_FORBIDDEN",
    ):
        status_code = 409
    else:
        status_code = 422
    return AccountError(error.code, field=error.field or None, status_code=status_code, params=error.params)


@router.get("/users", dependencies=[Depends(require_admin)])
def users(
    q: str = Query("", max_length=200),
    role: str = Query(""),
    account_status: str = Query("all", alias="status"),
    archived: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    enabled = True if account_status == "enabled" else False if account_status == "disabled" else None
    safe_role = role if role in ("customer", "sales", "admin") else ""
    total = count_users(archived=archived, query=q, role=safe_role, enabled=enabled)
    items = list_users(archived=archived, query=q, role=safe_role, enabled=enabled, limit=page_size, offset=(page - 1) * page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/audit-logs", dependencies=[Depends(require_admin)])
def audit_logs():
    return {"items": list_audit_logs()}


@router.get("/products")
def products():
    return {"items": list_admin_products()}

@router.post("/products", status_code=status.HTTP_201_CREATED)
def add_product(payload: ProductCreateRequest):
    if not payload.id.strip() or not payload.name.strip(): raise HTTPException(status_code=422, detail="Device model and name are required")
    if payload.base_price < 0 or payload.price_usd < 0: raise HTTPException(status_code=422, detail="Price cannot be negative")
    try: return create_product(payload.model_dump())
    except sqlite3.IntegrityError: raise HTTPException(status_code=409, detail="Device already exists")


@router.get("/config-catalog")
def config_catalog():
    return {"items": list_config_categories()}


@router.get("/catalog-tree")
def catalog_tree(include_disabled: bool = True):
    return {"items": get_catalog_tree(include_disabled)}


@router.post("/catalog/translation-draft")
def create_translation_draft(payload: TranslationDraftRequest, request: Request):
    _enforce_catalog_request_size(request)
    if len(payload.values) > 20 or any(len(str(value)) > 10000 for value in payload.values.values()):
        raise AccountError("CATALOG_TRANSLATION_REQUEST_TOO_LARGE", field="values", status_code=413)
    return {"items": {key: translation_draft(value) for key, value in payload.values.items()}}


@router.post("/catalog/categories", status_code=status.HTTP_201_CREATED)
def add_catalog_category_v2(payload: CatalogCategoryCreateV2Request, request: Request, user=Depends(require_catalog_manager)):
    _enforce_catalog_request_size(request)
    try:
        result = create_catalog_category(**payload.model_dump())
    except CatalogValidationError as error:
        raise _catalog_error(error)
    write_audit(
        user["id"],
        "catalog_category_create",
        "categories",
        result["id"],
        {"parent_id": result["parent_id"], "catalog_type": result["catalog_type"]},
    )
    return result


@router.patch("/catalog/categories/{category_id}")
def edit_catalog_category_v2(category_id: str, payload: CatalogCategoryUpdateV2Request, request: Request, user=Depends(require_catalog_manager)):
    _enforce_catalog_request_size(request)
    values = payload.model_dump(exclude={"parent_id"})
    try:
        result = update_catalog_category_v2(category_id, **values)
    except CatalogValidationError as error:
        raise _catalog_error(error)
    write_audit(
        user["id"],
        "catalog_category_update",
        "categories",
        category_id,
        {"version": result["version"], "enabled": result["enabled"]},
    )
    return result


@router.delete("/catalog/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_catalog_category_v2(category_id: str, user=Depends(require_catalog_manager)):
    try:
        delete_catalog_category_v2(category_id)
    except CatalogValidationError as error:
        raise _catalog_error(error)
    write_audit(user["id"], "catalog_category_delete", "categories", category_id)
    return None


@router.post("/catalog/items", status_code=status.HTTP_201_CREATED)
def add_catalog_item_v2(payload: CatalogItemV2Request, request: Request, user=Depends(require_catalog_manager)):
    _enforce_catalog_request_size(request)
    try:
        result = create_catalog_item(**payload.model_dump())
    except CatalogValidationError as error:
        raise _catalog_error(error)
    write_audit(
        user["id"],
        "catalog_item_create",
        "options",
        result["id"],
        {"category_id": result["category_id"], "catalog_type": result["catalog_type"], "code": result["code"]},
    )
    return result


@router.patch("/catalog/items/{option_id}")
def edit_catalog_item_v2(option_id: str, payload: CatalogItemUpdateV2Request, request: Request, user=Depends(require_catalog_manager)):
    _enforce_catalog_request_size(request)
    try:
        result = update_catalog_item(option_id, **payload.model_dump())
    except CatalogValidationError as error:
        raise _catalog_error(error)
    write_audit(
        user["id"],
        "catalog_item_update",
        "options",
        option_id,
        {"version": result["version"], "enabled": result["enabled"], "category_id": result["category_id"]},
    )
    return result


@router.put("/catalog/items-order")
def reorder_catalog_items_v2(payload: CatalogOrderRequest, user=Depends(require_catalog_manager)):
    try:
        result = reorder_catalog_items(payload.category_id, [item.model_dump() for item in payload.items])
    except CatalogValidationError as error:
        raise _catalog_error(error)
    write_audit(user["id"], "catalog_items_reorder", "categories", payload.category_id, {"item_count": len(result)})
    return {"items": result}


@router.post("/catalog/items/{option_id}/disable")
def disable_catalog_item_v2(option_id: str, payload: VersionedCatalogActionRequest, user=Depends(require_catalog_manager)):
    try:
        result = disable_catalog_item(option_id, version=payload.version)
    except CatalogValidationError as error:
        raise _catalog_error(error)
    write_audit(user["id"], "catalog_item_disable", "options", option_id, {"version": result["version"]})
    return result


@router.delete("/catalog/items/{option_id}")
def remove_catalog_item_v2(option_id: str, version: int = Query(..., ge=1), user=Depends(require_catalog_manager)):
    try:
        result = delete_catalog_item(option_id, version=version)
    except CatalogValidationError as error:
        raise _catalog_error(error)
    write_audit(user["id"], "catalog_item_delete", "options", option_id, result)
    return result


@router.patch("/config-catalog/options/{option_id}")
def edit_config_option(option_id: str, payload: ConfigOptionUpdateRequest):
    values = payload.model_dump(exclude_unset=True)
    if any(values.get(field) is not None and values[field] < 0 for field in ("price", "price_usd")):
        raise HTTPException(status_code=422, detail="Price cannot be negative")
    result = update_config_option(option_id, values)
    if result is None: raise HTTPException(status_code=404, detail="Configuration option not found")
    return result


@router.get("/config-catalog/options/{option_id}/references")
def option_references(option_id: str):
    result = config_option_references(option_id)
    if result is None: raise HTTPException(status_code=404, detail="Configuration option not found")
    return result


@router.delete("/config-catalog/options/{option_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_config_option(option_id: str):
    result = delete_config_option(option_id)
    if result is None: raise HTTPException(status_code=404, detail="Configuration option not found")
    if result is False: raise HTTPException(status_code=409, detail="Configuration option is still used by one or more devices")
    return None


@router.post("/config-catalog/categories", status_code=status.HTTP_201_CREATED)
def add_config_category(payload: ConfigCategoryCreateRequest):
    if not payload.name.strip(): raise HTTPException(status_code=422, detail="Category name is required")
    return create_config_category(payload.name, payload.description, payload.multiple, payload.name_en, payload.description_en)

@router.patch("/config-catalog/categories/{category_id}")
def edit_config_category(category_id: str, payload: ConfigCategoryUpdateRequest):
    result = update_config_category(category_id, payload.model_dump(exclude_unset=True))
    if result is None: raise HTTPException(status_code=404, detail="Configuration category not found")
    return result


@router.get("/config-catalog/categories/{category_id}/references")
def category_references(category_id: str):
    result = config_category_references(category_id)
    if result is None: raise HTTPException(status_code=404, detail="Configuration category not found")
    return result


@router.delete("/config-catalog/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_config_category(category_id: str):
    result = delete_config_category(category_id)
    if result is None: raise HTTPException(status_code=404, detail="Configuration category not found")
    if result is False: raise HTTPException(status_code=409, detail="Built-in or non-empty categories cannot be deleted")
    return None


@router.post("/config-catalog/options", status_code=status.HTTP_201_CREATED)
def add_config_option(payload: ConfigOptionCreateRequest):
    if not payload.code.strip() or not payload.name.strip(): raise HTTPException(status_code=422, detail="Option code and name are required")
    if any(value is not None and value < 0 for value in (payload.price, payload.price_usd)): raise HTTPException(status_code=422, detail="Price cannot be negative")
    values = payload.model_dump(exclude={"category_id", "code", "name"})
    return create_config_option(payload.category_id, payload.code, payload.name, **values)


@router.get("/products/{product_id}")
def product(product_id: str):
    result = get_admin_product(product_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return result


@router.get("/products/{product_id}/editor")
def product_editor(product_id: str):
    result = get_product_editor(product_id)
    if result is None:
        raise AccountError("CATALOG_PRODUCT_NOT_FOUND", field="product_id", status_code=404)
    return result


@router.put("/products/{product_id}/editor")
def replace_product_editor(product_id: str, payload: ProductEditorV2Request, request: Request, user=Depends(require_catalog_manager)):
    _enforce_catalog_request_size(request)
    try:
        result = save_product_editor(
            product_id,
            version=payload.version,
            model=payload.model,
            product_name_zh=payload.product_name_zh,
            product_name_en=payload.product_name_en,
            overview_zh=payload.overview_zh,
            overview_en=payload.overview_en,
            translation_status=payload.translation_status,
            enabled=payload.enabled,
            groups=[item.model_dump() for item in payload.base_option_groups],
            variants=[item.model_dump() for item in payload.price_variants],
            optional_config_ids=payload.optional_config_ids,
            optional_config_overrides={
                option_id: override.model_dump()
                for option_id, override in payload.optional_config_overrides.items()
            },
            colors=[item.model_dump() for item in payload.colors],
            specifications=[item.model_dump() for item in payload.specifications],
        )
    except CatalogValidationError as error:
        raise _catalog_error(error)
    write_audit(
        user["id"],
        "product_editor_v2_update",
        "products",
        product_id,
        {
            "version": result["version"],
            "base_group_count": len(result["base_option_groups"]),
            "price_variant_count": len(result["price_variants"]),
            "optional_config_count": len(result["optional_config_ids"]),
        },
    )
    return result


@router.patch("/products/{product_id}")
def edit_product(product_id: str, payload: ProductUpdateRequest):
    values = payload.model_dump(exclude_unset=True)
    if any(values.get(field) is not None and values[field] < 0 for field in ("base_price", "price_usd")):
        raise HTTPException(status_code=422, detail="Price cannot be negative")
    result = update_product(product_id, values)
    if result is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return result


@router.put("/products/{product_id}/configuration")
def save_product(product_id: str, payload: ProductSaveRequest):
    values = payload.model_dump(exclude={"colors", "option_ids", "option_overrides"}, exclude_unset=True)
    if any(values.get(field) is not None and values[field] < 0 for field in ("base_price", "price_usd")):
        raise HTTPException(status_code=422, detail="Price cannot be negative")
    colors = [{**color.model_dump(), "label": color.label.strip(), "label_en": color.label_en.strip() or color.label.strip()} for color in payload.colors]
    codes = [color["code"].strip() for color in colors]
    if not colors or any(not code or not color["label"] for code, color in zip(codes, colors)) or len(codes) != len(set(codes)):
        raise HTTPException(status_code=422, detail="Color codes must be unique and non-empty")
    if not any(color["is_default"] for color in colors):
        colors[0]["is_default"] = True
    elif sum(1 for color in colors if color["is_default"]) > 1:
        raise HTTPException(status_code=422, detail="Only one default color is allowed")
    overrides = {option_id: item.model_dump() for option_id, item in payload.option_overrides.items()}
    try:
        result = save_product_configuration(product_id, values, colors, payload.option_ids, overrides, {key: value.model_dump() for key, value in payload.motor_prices.items()}, [item.model_dump() for item in payload.specifications])
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    if result is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return result


@router.put("/products/{product_id}/colors")
def edit_product_colors(product_id: str, payload: ProductColorsRequest):
    if not payload.colors:
        raise HTTPException(status_code=422, detail="At least one color is required")
    codes = [color.code.strip() for color in payload.colors]
    if any(not code for code in codes) or len(codes) != len(set(codes)):
        raise HTTPException(status_code=422, detail="Color codes must be unique and non-empty")
    colors = [{**color.model_dump(), "label": color.label.strip(), "label_en": color.label_en.strip() or color.label.strip()} for color in payload.colors]
    if any(not color["label"] for color in colors):
        raise HTTPException(status_code=422, detail="Color names must be non-empty")
    if not any(color["is_default"] for color in colors):
        colors[0]["is_default"] = True
    elif sum(1 for color in colors if color["is_default"]) > 1:
        raise HTTPException(status_code=422, detail="Only one default color is allowed")
    result = replace_colors(product_id, colors)
    if result is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return result


@router.put("/products/{product_id}/options")
def edit_product_options(product_id: str, payload: ProductMappingsRequest):
    try:
        result = replace_option_mappings(product_id, payload.option_ids)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    if result is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return result

@router.patch("/products/{product_id}/options/{option_id}")
def edit_product_option_override(product_id: str, option_id: str, payload: ProductOptionOverrideRequest):
    result = update_product_option_override(product_id, option_id, payload.description_override, payload.description_override_en, payload.price_override)
    if result is None: raise HTTPException(status_code=404, detail="Product option mapping not found")
    return result


@router.post("/users", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
def add_user(payload: CreateStaffRequest, current=Depends(require_admin)):
    email = normalize_email(payload.email)
    phone = normalize_phone(payload.phone_country, payload.phone) if payload.phone else None
    validate_contact(email, phone)
    display_name = validate_display_name(payload.display_name)
    password = validate_password(payload.password)
    role = validate_role(payload.role)
    conflict = contact_conflict_field(email, phone)
    if conflict:
        raise AccountError("ACCOUNT_PHONE_DUPLICATE" if conflict == "phone" else "ACCOUNT_EMAIL_DUPLICATE", field=conflict, status_code=409)
    try:
        result = create_user(
            email, phone, password, role=role, display_name=display_name, phone_country=payload.phone_country.upper() if phone else None,
        )
    except sqlite3.IntegrityError:
        conflict = contact_conflict_field(email, phone)
        raise AccountError("ACCOUNT_PHONE_DUPLICATE" if conflict == "phone" else "ACCOUNT_EMAIL_DUPLICATE", field=conflict or "contact", status_code=409)
    write_audit(current["id"], "account_create", "users", result["id"], {"role": result["role"], "changed_fields": ["display_name", "role", "email", "phone", "password"]})
    return result


@router.patch("/users/{user_id}/status", dependencies=[Depends(require_admin)])
def update_user_status(user_id: str, payload: UserStatusRequest, current=Depends(require_admin)):
    target = get_user_by_id(user_id)
    if target is None:
        raise AccountError("ACCOUNT_NOT_FOUND", status_code=404)
    if target.get("archived"):
        raise AccountError("ACCOUNT_ARCHIVED", status_code=409)
    if not payload.enabled and user_id == current["id"]:
        raise AccountError("ACCOUNT_SELF_DISABLE_FORBIDDEN")
    if not payload.enabled and target["role"] == "admin":
        enabled_admins = count_users(role="admin", enabled=True)
        if enabled_admins <= 1:
            raise AccountError("ACCOUNT_LAST_ADMIN_REQUIRED")
    user = set_user_enabled(user_id, payload.enabled, payload.version)
    if user is None:
        raise AccountError("ACCOUNT_NOT_FOUND", status_code=404)
    write_audit(current["id"], "account_enable" if payload.enabled else "account_disable", "users", user_id, {"before": target["enabled"], "after": payload.enabled})
    return user

@router.patch("/users/{user_id}", dependencies=[Depends(require_admin)])
def edit_user(user_id: str, payload: UserUpdateRequest, current=Depends(require_admin)):
    values = payload.model_dump(exclude_unset=True)
    existing = get_user_by_id(user_id)
    if existing is None: raise AccountError("ACCOUNT_NOT_FOUND", status_code=404)
    if existing.get("archived"): raise AccountError("ACCOUNT_ARCHIVED", status_code=409)
    for field in ("email", "phone"):
        if field in values and values[field] is not None:
            values[field] = values[field].strip().lower() if field == "email" else values[field].strip()
            values[field] = values[field] or None
    if "email" in values: values["email"] = normalize_email(values["email"])
    if "phone_country" in values:
        values["phone_country"] = (values["phone_country"] or "").upper() or None
    if "phone" in values:
        if not values["phone"]:
            values["phone"] = None
            values["phone_country"] = None
        else:
            country = values.get("phone_country") or existing.get("phone_country")
            values["phone"] = normalize_phone(country, values["phone"])
            values["phone_country"] = country
    elif "phone_country" in values:
        raise AccountError("ACCOUNT_PHONE_INVALID", field="phone")
    if "email" in values or "phone" in values:
        validate_contact(values.get("email", existing.get("email")), values.get("phone", existing.get("phone")))
    if "display_name" in values: values["display_name"] = validate_display_name(values["display_name"])
    if values.get("password") is not None: values["password"] = validate_password(values["password"])
    if "role" in values: values["role"] = validate_role(values["role"])
    if not values.get("email", existing.get("email")) and not values.get("phone", existing.get("phone")):
        raise AccountError("ACCOUNT_CONTACT_REQUIRED", field="contact")
    if "display_name" in values:
        values["display_name"] = values["display_name"].strip()
        if not values["display_name"]: raise AccountError("ACCOUNT_NAME_REQUIRED", field="display_name")
    if existing["role"] == "admin" and "role" in values and values["role"] != "admin":
        enabled_admins = count_users(role="admin", enabled=True)
        if enabled_admins <= 1:
            raise AccountError("ACCOUNT_LAST_ADMIN_REQUIRED")
    if user_id == current["id"] and values.get("role") and values["role"] != "admin":
        raise AccountError("ACCOUNT_SELF_ROLE_CHANGE_FORBIDDEN", field="role")
    expected_version = values.pop("version")
    changed_fields = [field for field in ("display_name", "email", "phone", "phone_country", "role", "password") if field in values]
    conflict = contact_conflict_field(values.get("email"), values.get("phone"), user_id)
    if conflict:
        raise AccountError("ACCOUNT_PHONE_DUPLICATE" if conflict == "phone" else "ACCOUNT_EMAIL_DUPLICATE", field=conflict, status_code=409)
    try:
        result = update_user(user_id, values, expected_version)
    except sqlite3.IntegrityError:
        conflict = contact_conflict_field(values.get("email"), values.get("phone"), user_id)
        raise AccountError("ACCOUNT_PHONE_DUPLICATE" if conflict == "phone" else "ACCOUNT_EMAIL_DUPLICATE", field=conflict or "contact", status_code=409)
    if result is None: raise AccountError("ACCOUNT_NOT_FOUND", status_code=404)
    write_audit(current["id"], "account_update", "users", user_id, {"changed_fields": changed_fields, "role_before": existing["role"], "role_after": result["role"]})
    return result


@router.patch("/users/{user_id}/role", dependencies=[Depends(require_admin)])
def update_user_role(user_id: str, payload: UserRoleRequest, current=Depends(require_admin)):
    existing = get_user_by_id(user_id)
    if existing is None: raise AccountError("ACCOUNT_NOT_FOUND", status_code=404)
    if existing.get("archived"): raise AccountError("ACCOUNT_ARCHIVED", status_code=409)
    role = validate_role(payload.role)
    if user_id == current["id"] and role != "admin": raise AccountError("ACCOUNT_SELF_ROLE_CHANGE_FORBIDDEN", field="role")
    if existing["role"] == "admin" and role != "admin":
        enabled_admins = count_users(role="admin", enabled=True)
        if enabled_admins <= 1: raise AccountError("ACCOUNT_LAST_ADMIN_REQUIRED")
    result = update_user(user_id, {"role": role}, payload.version)
    if result is None: raise AccountError("ACCOUNT_NOT_FOUND", status_code=404)
    write_audit(current["id"], "account_role_change", "users", user_id, {"before": existing["role"], "after": role})
    return result


@router.patch("/users/{user_id}/password", dependencies=[Depends(require_admin)])
def reset_user_password(user_id: str, payload: UserPasswordResetRequest, current=Depends(require_admin)):
    existing = get_user_by_id(user_id)
    if existing is None: raise AccountError("ACCOUNT_NOT_FOUND", status_code=404)
    if existing.get("archived"): raise AccountError("ACCOUNT_ARCHIVED", status_code=409)
    password = validate_password(payload.password)
    result = update_user(user_id, {"password": password}, payload.version)
    if result is None: raise AccountError("ACCOUNT_NOT_FOUND", status_code=404)
    write_audit(current["id"], "account_password_reset", "users", user_id, {"changed_fields": ["password"]})
    return result


@router.post("/users/{user_id}/archive", dependencies=[Depends(require_admin)])
def archive_account(user_id: str, payload: UserArchiveRequest, current=Depends(require_admin)):
    existing = get_user_by_id(user_id)
    if existing is None: raise AccountError("ACCOUNT_NOT_FOUND", status_code=404)
    if user_id == current["id"]: raise AccountError("ACCOUNT_SELF_ARCHIVE_FORBIDDEN")
    if existing.get("archived"): raise AccountError("ACCOUNT_ARCHIVED", status_code=409)
    if existing["role"] == "admin" and existing["enabled"]:
        enabled_admins = count_users(role="admin", enabled=True)
        if enabled_admins <= 1: raise AccountError("ACCOUNT_LAST_ADMIN_REQUIRED")
    result = archive_user(user_id, current["id"], payload.reason, payload.version)
    if result is None: raise AccountError("ACCOUNT_NOT_FOUND", status_code=404)
    write_audit(current["id"], "account_archive", "users", user_id, {"reason": payload.reason[:200], "role": existing["role"]})
    return result


@router.post("/users/{user_id}/restore", dependencies=[Depends(require_admin)])
def restore_account(user_id: str, payload: UserRestoreRequest, current=Depends(require_admin)):
    if get_user_by_id(user_id) is None: raise AccountError("ACCOUNT_NOT_FOUND", status_code=404)
    result = restore_user(user_id, payload.version)
    if result is None: raise AccountError("ACCOUNT_NOT_FOUND", status_code=404)
    write_audit(current["id"], "account_restore", "users", user_id, {"role": result["role"]})
    return result


@router.get("/shares")
def shares(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), query: str = "",
    status_filter: str = Query("all", alias="status"), product_id: str = "",
    created_from: str = "", created_to: str = "",
):
    return search_all_shares(page, page_size, query, status_filter, product_id, created_from, created_to)


class ShareStatusRequest(BaseModel):
    active: bool


@router.patch("/shares/{share_id}/status", dependencies=[Depends(require_admin)])
def set_share_status(share_id: str, payload: ShareStatusRequest, current=Depends(require_admin)):
    if not set_any_share_active(share_id, payload.active):
        raise HTTPException(status_code=404, detail="Share not found")
    write_audit(current["id"], "share_reopen" if payload.active else "share_close", "shares", share_id, {"active": payload.active})
    return {"id": share_id, "active": payload.active}


@router.delete("/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
def close_share(share_id: str, current=Depends(require_admin)):
    if not deactivate_any_share(share_id):
        raise HTTPException(status_code=404, detail="Share not found")
    write_audit(current["id"], "share_close", "config_shares", share_id, {"active": False, "legacy_endpoint": True})
    return None
