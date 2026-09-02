"""Shared validation and normalization rules for account entry points."""
import re
from typing import Optional
from .phone_countries import get_country

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+[1-9][0-9]{6,14}$")
ALLOWED_ROLES = {"customer", "sales", "admin"}

def normalize_email(value: Optional[str]) -> Optional[str]:
    if value is None: return None
    value = value.strip().lower()
    if not value: return None
    if not EMAIL_RE.match(value): raise ValueError("邮箱格式无效")
    return value

def normalize_phone(country: Optional[str], value: Optional[str]) -> Optional[str]:
    if value is None: return None
    value = re.sub(r"\s+", "", value.strip())
    if not value: return None
    record = get_country(country or "")
    if record is None: raise ValueError("请选择有效国家")
    if not value.isdigit(): raise ValueError("手机号只能填写数字")
    minimum, maximum = record[4], record[5]
    if not minimum <= len(value) <= maximum:
        raise ValueError("该国家的手机号长度无效")
    return record[3] + value

def phone_national(country: Optional[str], e164: Optional[str]) -> Optional[str]:
    record = get_country(country or "")
    if not e164: return None
    if record and e164.startswith(record[3]): return e164[len(record[3]):]
    return e164.lstrip("+")

def validate_display_name(value: str) -> str:
    value = (value or "").strip()
    if not value: raise ValueError("姓名不能为空")
    if len(value) > 100: raise ValueError("姓名不能超过 100 个字符")
    return value

def validate_password(value: str) -> str:
    if len(value or "") < 8: raise ValueError("密码至少需要 8 个字符")
    if len(value) > 128: raise ValueError("密码不能超过 128 个字符")
    return value

def validate_role(value: str) -> str:
    if value not in ALLOWED_ROLES: raise ValueError("Unsupported role")
    return value

def validate_contact(email: Optional[str], phone: Optional[str]) -> None:
    if not email and not phone: raise ValueError("邮箱或手机号至少填写一项")
