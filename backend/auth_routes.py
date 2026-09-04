import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from .user_repository import (
    authenticate,
    create_guest,
    create_session,
    create_user,
    get_user_by_token,
    revoke_session,
    update_user,
    verify_user_password,
    contact_conflict_field,
)
from .rate_limit import clear, enforce
from .account_validation import normalize_email, normalize_phone, validate_display_name, validate_password
from .phone_countries import public_countries
from .account_errors import AccountError


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    phone_country: Optional[str] = None
    password: str
    display_name: str = ""


class LoginRequest(BaseModel):
    identifier: Optional[str] = None
    phone: Optional[str] = None
    phone_country: Optional[str] = None
    password: str


class ContactUpdateRequest(BaseModel):
    current_password: str
    email: Optional[str] = None
    phone: Optional[str] = None
    phone_country: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


def bearer_token(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AccountError("ACCOUNT_SESSION_EXPIRED", status_code=401)
    return authorization.split(" ", 1)[1].strip()


def current_user(request: Request, token: str = Depends(bearer_token)):
    user = get_user_by_token(token)
    if user is None:
        raise AccountError("ACCOUNT_SESSION_EXPIRED", status_code=401)
    request.state.current_user = user
    return user


def require_admin(user=Depends(current_user)):
    if user["role"] != "admin":
        raise AccountError("ACCOUNT_PERMISSION_DENIED", status_code=403)
    return user


def require_catalog_manager(user=Depends(current_user)):
    if user["role"] not in ("admin", "sales"):
        raise AccountError("ACCOUNT_PERMISSION_DENIED", status_code=403)
    return user


@router.post("/guest")
def guest_session(request: Request):
    client = request.client.host if request.client else "unknown"
    enforce("guest:{}".format(client), limit=30, window_seconds=3600)
    user = create_guest()
    return {"user": user, "session": create_session(user)}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request):
    client = request.client.host if request.client else "unknown"
    enforce("register:{}".format(client), limit=10, window_seconds=3600)
    email = normalize_email(payload.email)
    phone = normalize_phone(payload.phone_country, payload.phone)
    validate_display_name(payload.display_name)
    validate_password(payload.password)
    if not email or not phone: raise AccountError("ACCOUNT_CONTACT_REQUIRED", field="contact")
    try:
        user = create_user(email, phone, payload.password, display_name=payload.display_name, phone_country=payload.phone_country)
    except sqlite3.IntegrityError:
        field = contact_conflict_field(email, phone)
        raise AccountError("ACCOUNT_PHONE_DUPLICATE" if field == "phone" else "ACCOUNT_EMAIL_DUPLICATE", field=field or "contact", status_code=409)
    return {"user": user, "session": create_session(user)}


@router.post("/login")
def login(payload: LoginRequest, request: Request):
    client = request.client.host if request.client else "unknown"
    identifier = (payload.identifier or "").strip().lower()
    if not identifier:
        identifier = normalize_phone(payload.phone_country, payload.phone) or ""
    if not identifier: raise AccountError("ACCOUNT_IDENTIFIER_REQUIRED", field="identifier")
    key = "login:{}:{}".format(client, identifier)
    enforce(key, limit=5, window_seconds=900)
    user = authenticate(identifier, payload.password)
    if user is None:
        raise AccountError("ACCOUNT_CREDENTIALS_INVALID", field="password", status_code=401)
    clear(key)
    return {"user": user, "session": create_session(user)}


@router.get("/me")
def me(user=Depends(current_user)):
    return user


@router.get("/countries")
def countries(lang: str = "zh"):
    return {"items": public_countries("en" if lang == "en" else "zh")}


@router.patch("/profile/contact")
def update_contact(payload: ContactUpdateRequest, user=Depends(current_user)):
    if not verify_user_password(user["id"], payload.current_password):
        raise AccountError("ACCOUNT_CURRENT_PASSWORD_INVALID", field="current_password")
    email = normalize_email(payload.email) if payload.email is not None else user.get("email")
    if payload.phone is None and payload.phone_country is None:
        country = user.get("phone_country")
        phone = normalize_phone(country, user.get("phone")) if user.get("phone") else None
    elif payload.phone is None or not payload.phone_country:
        raise AccountError("ACCOUNT_PHONE_INVALID", field="phone")
    else:
        country = payload.phone_country.upper()
        phone = normalize_phone(country, payload.phone)
    if not email and not phone: raise AccountError("ACCOUNT_CONTACT_REQUIRED", field="contact")
    try:
        result = update_user(user["id"], {"email": email, "phone": phone, "phone_country": country})
    except sqlite3.IntegrityError:
        field = contact_conflict_field(email, phone, user["id"])
        raise AccountError("ACCOUNT_PHONE_DUPLICATE" if field == "phone" else "ACCOUNT_EMAIL_DUPLICATE", field=field or "contact", status_code=409)
    return result


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(payload: PasswordChangeRequest, user=Depends(current_user)):
    if not verify_user_password(user["id"], payload.current_password):
        raise AccountError("ACCOUNT_CURRENT_PASSWORD_INVALID", field="current_password")
    if payload.new_password != payload.confirm_password:
        raise AccountError("ACCOUNT_PASSWORD_CONFIRMATION_MISMATCH", field="confirm_password")
    validate_password(payload.new_password)
    update_user(user["id"], {"password": payload.new_password})
    return None


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: str = Depends(bearer_token)):
    revoke_session(token)
    return None
