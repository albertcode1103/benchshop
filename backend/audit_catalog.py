"""Audit catalog translations, prices, images and product mappings."""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from .config import PROJECT_DIR, UPLOAD_DIR
from .database import get_connection


def issue(level: str, code: str, message: str, record: str = "") -> Dict[str, str]:
    return {"level": level, "code": code, "record": record, "message": message}


def audit_catalog() -> Dict[str, Any]:
    findings: List[Dict[str, str]] = []
    with get_connection() as database:
        products = [dict(row) for row in database.execute("SELECT * FROM products ORDER BY sort_order, id")]
        categories = [dict(row) for row in database.execute("SELECT * FROM categories ORDER BY sort_order, id")]
        options = [dict(row) for row in database.execute("SELECT * FROM options ORDER BY category_id, sort_order, id")]
        mappings = [dict(row) for row in database.execute("SELECT * FROM product_options ORDER BY product_id, sort_order")]
        colors = [dict(row) for row in database.execute("SELECT * FROM product_colors ORDER BY product_id, sort_order")]
        foreign_key_errors = [tuple(row) for row in database.execute("PRAGMA foreign_key_check")]

    for table_name, rows, required_fields in (
        ("product", products, ("name", "title_name", "name_en", "title_name_en")),
        ("category", categories, ("name", "name_en")),
        ("option", options, ("code", "name", "name_en")),
    ):
        for row in rows:
            record = str(row.get("id", ""))
            for field in required_fields:
                if not str(row.get(field) or "").strip():
                    findings.append(issue("error", "missing_{}".format(field), "{} is empty".format(field), "{}:{}".format(table_name, record)))
            for field in ("name", "name_en", "description", "description_en", "title_name", "title_name_en"):
                text = str(row.get(field) or "")
                if "\ufffd" in text or "??" in text:
                    findings.append(issue("error", "invalid_text", "{} contains replacement characters or repeated question marks".format(field), "{}:{}".format(table_name, record)))

    option_codes = Counter(str(row.get("code") or "").strip().upper() for row in options)
    for code, count in option_codes.items():
        if code and count > 1:
            findings.append(issue("warning", "duplicate_option_code", "{} records use this code".format(count), code))

    for row in products:
        product_id = row["id"]
        product_colors = [color for color in colors if color["product_id"] == product_id]
        product_mappings = [mapping for mapping in mappings if mapping["product_id"] == product_id and mapping["enabled"]]
        if row["enabled"] and not product_colors:
            findings.append(issue("error", "product_without_color", "Enabled product has no colors", product_id))
        default_count = sum(bool(color["is_default"]) for color in product_colors)
        if product_colors and default_count != 1:
            findings.append(issue("error", "invalid_default_color", "Expected one default color, found {}".format(default_count), product_id))
        if row["enabled"] and not product_mappings:
            findings.append(issue("error", "product_without_options", "Enabled product has no mapped options", product_id))
        for field in ("base_price", "price_usd"):
            if float(row.get(field) or 0) <= 0:
                findings.append(issue("warning", "missing_price", "{} is not filled".format(field), "product:{}".format(product_id)))

    category_counts = Counter(row["category_id"] for row in options)
    for row in categories:
        if category_counts[row["id"]] == 0:
            findings.append(issue("warning", "empty_category", "Category has no options", row["id"]))

    mapped_options = {row["option_id"] for row in mappings}
    for row in options:
        option_id = row["id"]
        if row["enabled"] and option_id not in mapped_options:
            findings.append(issue("warning", "unmapped_option", "Enabled option is not mapped to a product", option_id))
        for field in ("price", "price_usd"):
            if float(row.get(field) or 0) <= 0:
                findings.append(issue("warning", "missing_price", "{} is not filled".format(field), "option:{}".format(option_id)))
        image_path = str(row.get("image_path") or "").strip()
        if not image_path:
            findings.append(issue("warning", "missing_image", "Configuration has no image", option_id))
        elif image_path.startswith("/api/v1/media/") and not (UPLOAD_DIR / Path(image_path).name).is_file():
            findings.append(issue("error", "broken_image", "Uploaded image does not exist: {}".format(image_path), option_id))
        elif not image_path.startswith("/api/v1/media/") and not image_path.lower().startswith(("http://", "https://")) and not (PROJECT_DIR / Path(image_path)).is_file():
            findings.append(issue("error", "broken_image", "Image path does not exist: {}".format(image_path), option_id))

    for color in colors:
        image_path = str(color.get("image_path") or "").strip()
        if image_path.startswith("/api/v1/media/") and not (UPLOAD_DIR / Path(image_path).name).is_file():
            findings.append(issue("error", "broken_image", "Uploaded color image does not exist: {}".format(image_path), "{}:{}".format(color["product_id"], color["code"])))
        elif image_path and not image_path.startswith("/api/v1/media/") and not image_path.lower().startswith(("http://", "https://")) and not (PROJECT_DIR / Path(image_path)).is_file():
            findings.append(issue("error", "broken_image", "Color image path does not exist: {}".format(image_path), "{}:{}".format(color["product_id"], color["code"])))

    for failure in foreign_key_errors:
        findings.append(issue("error", "foreign_key", "Foreign-key check failed: {}".format(failure)))

    counts = Counter(item["level"] for item in findings)
    return {
        "summary": {
            "products": len(products),
            "categories": len(categories),
            "options": len(options),
            "mappings": len(mappings),
            "errors": counts["error"],
            "warnings": counts["warning"],
        },
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit BOTEN catalog data")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="Return a failure code for warnings too")
    arguments = parser.parse_args()
    report = audit_catalog()
    if arguments.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        summary = report["summary"]
        print("Products: {products}; categories: {categories}; options: {options}; mappings: {mappings}".format(**summary))
        print("Errors: {errors}; warnings: {warnings}".format(**summary))
        for item in report["findings"]:
            print("[{level}] {code} {record}: {message}".format(**item))
    has_errors = report["summary"]["errors"] > 0
    has_warnings = report["summary"]["warnings"] > 0
    raise SystemExit(1 if has_errors or (arguments.strict and has_warnings) else 0)


if __name__ == "__main__":
    main()
