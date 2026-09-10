"""Canonical catalog codes and display names for configs, tools and accessories."""

import re
from typing import Any, Iterable


_PREFIXES = ("BTE", "BTK", "BTC", "BT")


def normalize_catalog_code(value: Any) -> str:
    raw = str(value or "").strip().upper()
    code = re.sub(r"\s+", "", raw)
    for prefix in _PREFIXES:
        match = re.fullmatch(r"{}-?([A-Z0-9]+)".format(prefix), code)
        if match:
            return "{}-{}".format(prefix, match.group(1))
    return raw


def strip_redundant_catalog_code(name: Any, code: Any, aliases: Iterable[Any] = ()) -> str:
    text = re.sub(r"\s+", " ", str(name or "")).strip()
    if not text:
        return ""
    candidates = {str(code or "").strip(), normalize_catalog_code(code)}
    candidates.update(str(alias or "").strip() for alias in aliases)
    candidates.update(normalize_catalog_code(alias) for alias in aliases)
    candidates.update(candidate.replace("-", "") for candidate in tuple(candidates))
    for candidate in sorted((item for item in candidates if item), key=len, reverse=True):
        pattern = r"^{}(?=$|[\s·:：/\\|_—–-])(?:[\s·:：/\\|_—–-]+)?".format(re.escape(candidate))
        updated = re.sub(pattern, "", text, count=1, flags=re.IGNORECASE).strip()
        if updated != text:
            text = updated
            break
    return text
