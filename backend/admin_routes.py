import sqlite3
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from .auth_routes import require_admin
from .user_repository import create_user, get_user_by_id, list_users, set_user_enabled, update_user
from .config_repository import deactivate_share, list_shares
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
)


router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class CreateStaffRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    password: str
    display_name: str = ""
    role: str = "sales"


class UserStatusRequest(BaseModel):
    enabled: bool

class UserUpdateRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
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
    image_path: Optional[str] = None
    is_default: bool = False


class ProductColorsRequest(BaseModel):
    colors: List[ProductColorRequest]


class ProductMappingsRequest(BaseModel):
    option_ids: List[str]

class ProductOptionOverrideRequest(BaseModel):
    description_override: Optional[str] = None
    description_override_en: Optional[str] = None
    price_override: Optional[int] = None


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


@router.get("/users")
def users():
    return {"items": list_users()}


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


@router.post("/config-catalog/categories", status_code=status.HTTP_201_CREATED)
def add_config_category(payload: ConfigCategoryCreateRequest):
    if not payload.name.strip(): raise HTTPException(status_code=422, detail="Category name is required")
    return create_config_category(payload.name, payload.description, payload.multiple, payload.name_en, payload.description_en)

@router.patch("/config-catalog/categories/{category_id}")
def edit_config_category(category_id: str, payload: ConfigCategoryUpdateRequest):
    result = update_config_category(category_id, payload.model_dump(exclude_unset=True))
    if result is None: raise HTTPException(status_code=404, detail="Configuration category not found")
    return result


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


@router.put("/products/{product_id}/colors")
def edit_product_colors(product_id: str, payload: ProductColorsRequest):
    if not payload.colors:
        raise HTTPException(status_code=422, detail="At least one color is required")
    codes = [color.code.strip() for color in payload.colors]
    if any(not code for code in codes) or len(codes) != len(set(codes)):
        raise HTTPException(status_code=422, detail="Color codes must be unique and non-empty")
    colors = [color.model_dump() for color in payload.colors]
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


@router.post("/users", status_code=status.HTTP_201_CREATED)
def add_user(payload: CreateStaffRequest):
    if payload.role not in ("customer", "sales", "admin"):
        raise HTTPException(status_code=422, detail="Unsupported role")
    if not payload.email and not payload.phone:
        raise HTTPException(status_code=422, detail="Email or phone is required")
    if len(payload.password) < 8:
        raise HTTPException(status_code=422, detail="Password must contain at least 8 characters")
    try:
        return create_user(
            payload.email.strip().lower() if payload.email else None,
            payload.phone.strip() if payload.phone else None,
            payload.password,
            role=payload.role,
            display_name=payload.display_name,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email or phone already exists")


@router.patch("/users/{user_id}/status")
def update_user_status(user_id: str, payload: UserStatusRequest):
    user = set_user_enabled(user_id, payload.enabled)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.patch("/users/{user_id}")
def edit_user(user_id: str, payload: UserUpdateRequest):
    values = payload.model_dump(exclude_unset=True)
    existing = get_user_by_id(user_id)
    if existing is None: raise HTTPException(status_code=404, detail="User not found")
    for field in ("email", "phone"):
        if field in values and values[field] is not None:
            values[field] = values[field].strip().lower() if field == "email" else values[field].strip()
            values[field] = values[field] or None
    if not values.get("email", existing.get("email")) and not values.get("phone", existing.get("phone")):
        raise HTTPException(status_code=422, detail="Email or phone is required")
    if "display_name" in values:
        values["display_name"] = values["display_name"].strip()
        if not values["display_name"]: raise HTTPException(status_code=422, detail="Display name is required")
    if values.get("role") and values["role"] not in ("customer", "sales", "admin"):
        raise HTTPException(status_code=422, detail="Unsupported role")
    if values.get("password") is not None and values["password"] and len(values["password"]) < 8:
        raise HTTPException(status_code=422, detail="Password must contain at least 8 characters")
    try:
        result = update_user(user_id, values)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email or phone already exists")
    if result is None: raise HTTPException(status_code=404, detail="User not found")
    return result


@router.get("/shares")
def shares():
    return {"items": list_shares()}


@router.delete("/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
def close_share(share_id: str):
    if not deactivate_share(share_id):
        raise HTTPException(status_code=404, detail="Share not found")
    return None
