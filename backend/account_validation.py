"""Shared validation and normalization rules for account entry points."""
import re
from typing import Optional
from .account_errors import AccountError
from .phone_countries import get_country

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+[1-9][0-9]{6,14}$")
ALLOWED_ROLES = {"customer", "sales", "admin"}

def normalize_email(value: Optional[str]) -> Optional[str]:
    if value is None: return None
    value = value.strip().lower()
    if not value: return None
    if not EMAIL_RE.match(value): raise AccountError("ACCOUNT_EMAIL_INVALID", field="email")
    return value

def normalize_phone(country: Optional[str], value: Optional[str]) -> Optional[str]:
    if value is None: return None
    value = re.sub(r"\s+", "", value.strip())
    if not value: return None
    record = get_country(country or "")
    if record is None: raise AccountError("ACCOUNT_PHONE_COUNTRY_INVALID", field="phone_country")
    if not value.isdigit(): raise AccountError("ACCOUNT_PHONE_INVALID", field="phone")
    minimum, maximum = record[4], record[5]
    if not minimum <= len(value) <= maximum:
        raise AccountError("ACCOUNT_PHONE_INVALID", field="phone")
    return record[3] + value

def phone_national(country: Optional[str], e164: Optional[str]) -> Optional[str]:
    record = get_country(country or "")
    if not e164: return None
    if record and e164.startswith(record[3]): return e164[len(record[3]):]
    return e164.lstrip("+")

def validate_display_name(value: str) -> str:
    value = (value or "").strip()
    if not value: raise AccountError("ACCOUNT_NAME_REQUIRED", field="display_name")
    if len(value) > 100: raise AccountError("ACCOUNT_NAME_TOO_LONG", field="display_name")
    return value

def validate_password(value: str) -> str:
    if len(value or "") < 8: raise AccountError("ACCOUNT_PASSWORD_TOO_SHORT", field="password")
    if len(value) > 128: raise AccountError("ACCOUNT_PASSWORD_TOO_LONG", field="password")
    return value

def validate_role(value: str) -> str:
    if value not in ALLOWED_ROLES: raise AccountError("ACCOUNT_ROLE_INVALID", field="role")
    return value

def validate_contact(email: Optional[str], phone: Optional[str]) -> None:
    if not email and not phone: raise AccountError("ACCOUNT_CONTACT_REQUIRED", field="contact")
