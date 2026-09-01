"""Dependency-free XLSX reader/writer for catalog maintenance workbooks."""
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _column_name(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _column_index(reference):
    value = 0
    for char in (char for char in reference if char.isalpha()):
        value = value * 26 + ord(char.upper()) - 64
    return value


def _sheet(rows):
    output = []
    for row_index, row in enumerate(rows, 1):
        cells = []
        for column_index, value in enumerate(row, 1):
            reference = f"{_column_name(column_index)}{row_index}"
            if isinstance(value, bool):
                cells.append(f'<c r="{reference}" t="b"><v>{int(value)}</v></c>')
            elif isinstance(value, (int, float)):
                cells.append(f'<c r="{reference}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value or ""))}</t></is></c>')
        output.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{MAIN}"><sheetData>{"".join(output)}</sheetData></worksheet>'


def catalog_template(products, categories, motor_prices=(), specifications=()):
    sheets = [
        ("设备目录", [["设备型号", "中文名称", "英文名称", "人民币参考价", "美元参考价", "启用"]] + [[p["id"], p["name"], p.get("name_en", ""), p.get("base_price", 0), p.get("price_usd", 0), p.get("enabled", True)] for p in products]),
        ("配置目录", [["配置编号", "分类编号", "中文名称", "英文名称", "中文描述", "英文描述", "备注", "人民币价格", "美元价格", "启用"]] + [[o["id"], c["id"], o["name"], o.get("name_en", ""), o.get("description", ""), o.get("description_en", ""), o.get("notes", ""), o.get("price", 0), o.get("price_usd", 0), o.get("enabled", True)] for c in categories for o in c.get("options", [])]),
        ("电机价格", [["设备型号", "电机配置编号", "人民币基础价", "美元基础价"]] + [[row["product_id"], row["motor_option_id"], row["base_price_cny"], row["base_price_usd"]] for row in motor_prices]),
        ("设备参数", [["设备型号", "参数ID", "中文项目", "英文项目", "中文数据", "英文数据", "排序"]] + [[row["product_id"], row["id"], row["label"], row["label_en"], row["value"], row["value_en"], row["sort_order"]] for row in specifications]),
    ]
    out = BytesIO()
    workbook_sheets = "".join(
        '<sheet name="{}" sheetId="{}" r:id="rId{}"/>'.format(escape(name), index, index)
        for index, (name, _) in enumerate(sheets, 1)
    )
    with ZipFile(out, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, 5)) + "</Types>")
        archive.writestr("xl/workbook.xml", f'<?xml version="1.0"?><workbook xmlns="{MAIN}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{workbook_sheets}</sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, 5)) + "</Relationships>")
        for index, (_, rows) in enumerate(sheets, 1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet(rows))
    return out.getvalue()


def _shared_strings(archive):
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.itertext()) for node in root.findall("{*}si")]


def _cell_value(cell, strings):
    kind = cell.get("t")
    if kind == "inlineStr":
        node = cell.find("{*}is")
        return "".join(node.itertext()) if node is not None else ""
    raw = cell.findtext("{*}v", default="")
    if kind == "s":
        return strings[int(raw)] if raw and int(raw) < len(strings) else ""
    if kind == "b":
        return raw in ("1", "true", "TRUE")
    return raw


def parse_xlsx(data):
    """Read exported and Excel/WPS-resaved files, preserving empty columns."""
    with ZipFile(BytesIO(data)) as archive:
        strings = _shared_strings(archive)
        paths = sorted((name for name in archive.namelist() if name.startswith("xl/worksheets/") and name.endswith(".xml")), key=lambda name: int("".join(char for char in name if char.isdigit()) or 0))
        if len(paths) < 4:
            raise ValueError("Workbook must contain four worksheets")
        sheets = []
        for path in paths[:4]:
            root = ET.fromstring(archive.read(path)); rows = []
            for row in root.findall("{*}sheetData/{*}row"):
                values = []
                for cell in row.findall("{*}c"):
                    position = _column_index(cell.get("r", "A1"))
                    while len(values) < position - 1:
                        values.append("")
                    values.append(_cell_value(cell, strings))
                rows.append(values)
            sheets.append(rows)
    return sheets
