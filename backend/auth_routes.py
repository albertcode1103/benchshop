import re
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
)
from .rate_limit import clear, enforce


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    password: str
    display_name: str = ""


class LoginRequest(BaseModel):
    identifier: str
    password: str


def bearer_token(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return authorization.split(" ", 1)[1].strip()


def current_user(token: str = Depends(bearer_token)):
    user = get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    return user


def require_admin(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
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
    email = payload.email.strip().lower() if payload.email else None
    phone = payload.phone.strip() if payload.phone else None
    if not email and not phone:
        raise HTTPException(status_code=422, detail="Email or phone is required")
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=422, detail="Invalid email")
    if phone and not re.match(r"^\+?[0-9]{7,15}$", phone):
        raise HTTPException(status_code=422, detail="Invalid phone")
    try:
        user = create_user(email, phone, payload.password, display_name=payload.display_name)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email or phone already exists")
    return {"user": user, "session": create_session(user)}


@router.post("/login")
def login(payload: LoginRequest, request: Request):
    client = request.client.host if request.client else "unknown"
    key = "login:{}:{}".format(client, payload.identifier.strip().lower())
    enforce(key, limit=5, window_seconds=900)
    user = authenticate(payload.identifier, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    clear(key)
    return {"user": user, "session": create_session(user)}


@router.get("/me")
def me(user=Depends(current_user)):
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: str = Depends(bearer_token)):
    revoke_session(token)
    return None
