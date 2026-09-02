import sqlite3
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .auth_routes import require_admin, require_catalog_manager
from .user_repository import create_user, get_user_by_id, list_users, set_user_enabled, update_user
from .config_repository import deactivate_share, list_shares
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


router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_catalog_manager)])

CATALOG_SHEET_HEADERS = [
    ["设备型号", "中文名称", "英文名称", "人民币参考价", "美元参考价", "启用"],
    ["配置编号", "分类编号", "中文名称", "英文名称", "中文描述", "英文描述", "备注", "人民币价格", "美元价格", "启用"],
    ["设备型号", "电机配置编号", "人民币基础价", "美元基础价"],
    ["设备型号", "参数ID", "中文项目", "英文项目", "中文数据", "英文数据", "排序"],
]

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

class UserUpdateRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    phone_country: Optional[str] = None
    display_name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None


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


@router.get("/users", dependencies=[Depends(require_admin)])
def users():
    return {"items": list_users()}


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
def add_user(payload: CreateStaffRequest):
    try:
        email = normalize_email(payload.email)
        phone = normalize_phone(payload.phone_country, payload.phone) if payload.phone else None
        validate_contact(email, phone)
        display_name = validate_display_name(payload.display_name)
        password = validate_password(payload.password)
        role = validate_role(payload.role)
        return create_user(
            email, phone, password, role=role, display_name=display_name, phone_country=payload.phone_country.upper() if phone else None,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email or phone already exists")


@router.patch("/users/{user_id}/status", dependencies=[Depends(require_admin)])
def update_user_status(user_id: str, payload: UserStatusRequest, current=Depends(require_admin)):
    target = get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not payload.enabled and user_id == current["id"]:
        raise HTTPException(status_code=422, detail="You cannot disable your own account")
    if not payload.enabled and target["role"] == "admin":
        enabled_admins = sum(1 for user in list_users() if user["role"] == "admin" and user["enabled"])
        if enabled_admins <= 1:
            raise HTTPException(status_code=422, detail="At least one enabled admin account is required")
    user = set_user_enabled(user_id, payload.enabled)
    return user

@router.patch("/users/{user_id}", dependencies=[Depends(require_admin)])
def edit_user(user_id: str, payload: UserUpdateRequest, current=Depends(require_admin)):
    values = payload.model_dump(exclude_unset=True)
    existing = get_user_by_id(user_id)
    if existing is None: raise HTTPException(status_code=404, detail="User not found")
    for field in ("email", "phone"):
        if field in values and values[field] is not None:
            values[field] = values[field].strip().lower() if field == "email" else values[field].strip()
            values[field] = values[field] or None
    try:
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
            raise ValueError("修改国家时必须同时填写手机号")
        if "email" in values or "phone" in values:
            validate_contact(values.get("email", existing.get("email")), values.get("phone", existing.get("phone")))
        if "display_name" in values: values["display_name"] = validate_display_name(values["display_name"])
        if values.get("password") is not None: values["password"] = validate_password(values["password"])
        if "role" in values: values["role"] = validate_role(values["role"])
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    if not values.get("email", existing.get("email")) and not values.get("phone", existing.get("phone")):
        raise HTTPException(status_code=422, detail="Email or phone is required")
    if "display_name" in values:
        values["display_name"] = values["display_name"].strip()
        if not values["display_name"]: raise HTTPException(status_code=422, detail="Display name is required")
    if values.get("role") and values["role"] not in ("customer", "sales", "admin"):
        raise HTTPException(status_code=422, detail="Unsupported role")
    if existing["role"] == "admin" and "role" in values and values["role"] != "admin":
        enabled_admins = sum(1 for user in list_users() if user["role"] == "admin" and user["enabled"])
        if enabled_admins <= 1:
            raise HTTPException(status_code=422, detail="At least one enabled admin account is required")
    if user_id == current["id"] and values.get("role") and values["role"] != "admin":
        raise HTTPException(status_code=422, detail="You cannot remove your own admin access")
    if values.get("password") is not None and values["password"] and len(values["password"]) < 8:
        raise HTTPException(status_code=422, detail="Password must contain at least 8 characters")
    try:
        result = update_user(user_id, values)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email or phone already exists")
    if result is None: raise HTTPException(status_code=404, detail="User not found")
    return result


@router.get("/shares", dependencies=[Depends(require_admin)])
def shares():
    return {"items": list_shares()}


@router.delete("/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
def close_share(share_id: str):
    if not deactivate_share(share_id):
        raise HTTPException(status_code=404, detail="Share not found")
    return None
