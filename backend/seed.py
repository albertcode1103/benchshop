import ast
import re
from pathlib import Path
from typing import Any, Dict

from .config import PROJECT_DIR
from .database import get_connection, initialize_database


SOURCE_PATH = PROJECT_DIR / "js" / "data.js"


def extract_literal(source: str, variable_name: str) -> Any:
    match = re.search(r"\bconst\s+" + re.escape(variable_name) + r"\s*=\s*", source)
    if not match:
        raise ValueError("Missing variable: " + variable_name)

    start = match.end()
    opening = source[start]
    closing = {"[": "]", "{": "}"}.get(opening)
    if not closing:
        raise ValueError("Unsupported literal for: " + variable_name)

    depth = 0
    quote = None
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ('"', "'"):
            quote = char
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                literal = source[start : index + 1]
                literal = re.sub(r"//[^\r\n]*", "", literal)
                literal = re.sub(
                    r"([\{,]\s*)([A-Za-z_$][A-Za-z0-9_$]*)(\s*:)",
                    r"\1'\2'\3",
                    literal,
                )
                literal = re.sub(r"\btrue\b", "True", literal)
                literal = re.sub(r"\bfalse\b", "False", literal)
                literal = re.sub(r"\bnull\b", "None", literal)
                return ast.literal_eval(literal)
    raise ValueError("Unclosed literal for: " + variable_name)


def model_id(type_name: str) -> str:
    return re.sub(r"\s+", "", re.sub(r"^BOTEN\s+", "", type_name, flags=re.I)).lower()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def option_code(option: Dict[str, Any]) -> str:
    return option["name"].split()[0].replace("-", "").upper()


def seed() -> None:
    initialize_database()
    source = SOURCE_PATH.read_text(encoding="utf-8")
    catalog = extract_literal(source, "cr1016Categories")
    products = extract_literal(source, "tbListData")
    mappings = extract_literal(source, "modelOptionMappings")
    overrides = extract_literal(source, "modelOptionOverrides")

    category_lookup = {category["id"]: category for category in catalog}
    option_lookup: Dict[str, Dict[str, Any]] = {}

    with get_connection() as connection:
        for category_index, category in enumerate(catalog):
            connection.execute(
                """
                INSERT INTO categories (id, name, description, multiple, sort_order)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    multiple = excluded.multiple,
                    sort_order = excluded.sort_order
                """,
                (
                    category["id"],
                    category["name"],
                    category.get("description", ""),
                    int(category.get("multiple", True)),
                    category_index + 2,
                ),
            )
            for option_index, option in enumerate(category["options"]):
                option_lookup[option["id"]] = option
                connection.execute(
                    """
                    INSERT INTO options
                        (id, category_id, code, name, name_en, description, image_path, price, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        category_id = excluded.category_id,
                        code = excluded.code,
                        name = excluded.name,
                        name_en = CASE WHEN options.name_en = '' THEN excluded.name_en ELSE options.name_en END,
                        description = excluded.description,
                        image_path = excluded.image_path,
                        price = excluded.price,
                        sort_order = excluded.sort_order
                    """,
                    (
                        option["id"],
                        category["id"],
                        option_code(option),
                        option["name"],
                        option["name"],
                        option.get("description", ""),
                        option.get("image"),
                        option.get("price", 0),
                        option_index,
                    ),
                )

        for category_index, (category_id, category_name) in enumerate(
            (("motor", "Motor | 电机配置"), ("voltage", "Power | 供电配置"))
        ):
            connection.execute(
                """
                INSERT INTO categories (id, name, description, multiple, sort_order)
                VALUES (?, ?, '', 0, ?)
                ON CONFLICT(id) DO UPDATE SET name = excluded.name, sort_order = excluded.sort_order
                """,
                (category_id, category_name, category_index),
            )

        for product_index, product in enumerate(products):
            product_id = model_id(product["type"])
            connection.execute(
                """
                INSERT INTO products (id, name, title_name, description, base_price, sort_order)
                VALUES (?, ?, ?, ?, 0, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    title_name = excluded.title_name,
                    sort_order = excluded.sort_order
                """,
                (product_id, product["type"], product["name"], "设备描述XXXX占位", product_index),
            )

            for color_index, color in enumerate(product.get("colors", [])):
                code = product["type"].replace("BOTEN ", "").strip()
                suffix = "绿色" if color == "Green" else "红色" if color == "Red" else color
                folder_code = "CR318 Pro" if code == "CR318 PRO" else code
                relative_image = "tb/tbpic/{0}/{0}{1}.png".format(folder_code, suffix) if len(product["colors"]) > 1 else "tb/tbpic/{0}/{0}.png".format(folder_code)
                image_path = relative_image if (PROJECT_DIR / relative_image).is_file() else None
                connection.execute(
                    """
                    INSERT INTO product_colors (product_id, code, label, label_en, image_path, is_default, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(product_id, code) DO UPDATE SET
                        label = excluded.label,
                        label_en = excluded.label_en,
                        image_path = excluded.image_path,
                        is_default = excluded.is_default,
                        sort_order = excluded.sort_order
                    """,
                    (product_id, color, suffix, color, image_path, int(color == "Green" or color_index == 0), color_index),
                )

            for spec_category, values in (("motor", product["motors"]), ("voltage", product["voltages"])):
                for option_index, value in enumerate(values):
                    option_id = spec_category + "-" + slug(value)
                    connection.execute(
                        """
                        INSERT INTO options (id, category_id, code, name, sort_order)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET name = excluded.name, sort_order = excluded.sort_order
                        """,
                        (option_id, spec_category, slug(value).upper(), value, option_index),
                    )
                    mapping_id = "{}-{}-{}".format(product_id.upper(), spec_category.upper(), slug(value).upper())
                    connection.execute(
                        """
                        INSERT INTO product_options (product_id, option_id, mapping_id, sort_order)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(product_id, option_id) DO UPDATE SET
                            mapping_id = excluded.mapping_id,
                            sort_order = excluded.sort_order
                        """,
                        (product_id, option_id, mapping_id, option_index),
                    )

            for category_id, option_ids in mappings.get(product_id, {}).items():
                if category_id not in category_lookup:
                    raise ValueError("Unknown category mapping: {}-{}".format(product_id, category_id))
                for option_index, option_id in enumerate(option_ids):
                    option = option_lookup.get(option_id)
                    if option is None:
                        raise ValueError("Unknown option mapping: {}-{}".format(product_id, option_id))
                    override = overrides.get(product_id, {}).get(option_id, {})
                    mapping_id = "{}-{}-{}".format(product_id.upper(), category_id.upper(), option_code(option))
                    connection.execute(
                        """
                        INSERT INTO product_options
                            (product_id, option_id, mapping_id, description_override, image_override, price_override, sort_order)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(product_id, option_id) DO UPDATE SET
                            mapping_id = excluded.mapping_id,
                            description_override = excluded.description_override,
                            image_override = excluded.image_override,
                            price_override = excluded.price_override,
                            sort_order = excluded.sort_order
                        """,
                        (
                            product_id,
                            option_id,
                            mapping_id,
                            override.get("description"),
                            override.get("image"),
                            override.get("price"),
                            option_index,
                        ),
                    )

    print("Seeded {} products and {} shared options.".format(len(products), len(option_lookup)))


if __name__ == "__main__":
    seed()
