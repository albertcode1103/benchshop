"""Stable export identity, independent of export date or UI language."""
import re

def pdf_identity(kind, number):
    value = str(number or "").strip()
    if kind == "share" and re.fullmatch(r"[0-9]{6}", value):
        return "ShareBench-BOTEN" + value
    prefixes = {"inquiry": ("BTI", "RFQ", 2), "quote": ("BTQ", "QUOTA", 4)}
    if kind in prefixes:
        original, output, width = prefixes[kind]
        match = re.fullmatch(original + r"-([0-9]{8})-([0-9]+)", value)
        if match:
            return f"{output}-BOTEN{match[1]}-{int(match[2]):0{width}d}"
    raise ValueError("Invalid historical document number; repair the source record before export")
