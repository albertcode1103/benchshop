"""Dependency-free XLSX reader/writer for catalog maintenance workbooks."""
from io import BytesIO
import re
from zipfile import ZIP_DEFLATED, ZipFile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _allowed_workbook_part(name):
    if name in {'[Content_Types].xml', '_rels/.rels', 'xl/workbook.xml',
                'xl/_rels/workbook.xml.rels', 'xl/styles.xml', 'xl/sharedStrings.xml',
                'xl/calcChain.xml', 'xl/metadata.xml',
                'docProps/core.xml', 'docProps/app.xml', 'docProps/custom.xml'}:
        return True
    if name in {'_rels/', 'xl/', 'xl/_rels/', 'xl/worksheets/',
                'xl/worksheets/_rels/', 'xl/theme/', 'docProps/'}:
        return True
    return bool(re.fullmatch(r'xl/(?:worksheets/sheet[1-9][0-9]*\.xml|'
                             r'worksheets/_rels/sheet[1-9][0-9]*\.xml\.rels|'
                             r'theme/theme[1-9][0-9]*\.xml)', name))


class _WorkbookTreeBuilder(ET.TreeBuilder):
    def doctype(self, name, pubid, system):
        raise ValueError("XML document types and entities are not supported")


def _parse_xml(data):
    return ET.fromstring(data, parser=ET.XMLParser(target=_WorkbookTreeBuilder()))


def _column_name(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _column_index(reference):
    match = re.fullmatch(r"([A-Za-z]+)[1-9][0-9]*", reference)
    if match is None:
        raise ValueError("Invalid worksheet cell reference")
    value = 0
    for char in match.group(1):
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
    root = _parse_xml(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.itertext()) for node in root.findall("{*}si")]


def _cell_value(cell, strings):
    kind = cell.get("t")
    if kind == "inlineStr":
        node = cell.find("{*}is")
        return "".join(node.itertext()) if node is not None else ""
    raw = cell.findtext("{*}v", default="")
    if kind == "s":
        try:
            index = int(raw)
        except (TypeError, ValueError):
            raise ValueError("Invalid shared string reference")
        if index < 0 or index >= len(strings):
            raise ValueError("Shared string reference is out of range")
        return strings[index]
    if kind == "b":
        return raw in ("1", "true", "TRUE")
    return raw


def _row_values(row, strings):
    cells = {}
    previous_position = 0
    for cell in row.findall("{*}c"):
        reference = cell.get("r")
        position = _column_index(reference) if reference else previous_position + 1
        if position < 1 or position > 128 or len(cells) >= 128:
            raise ValueError("Too many worksheet columns")
        if position in cells:
            raise ValueError("Duplicate worksheet cell reference")
        value = _cell_value(cell, strings)
        if len(str(value)) > 10000:
            raise ValueError("Cell text exceeds limits")
        cells[position] = value
        previous_position = position
    return [cells.get(position, "") for position in range(1, max(cells, default=0) + 1)]


def parse_xlsx(data):
    """Read exported and Excel/WPS-resaved files, preserving empty columns."""
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Workbook is too large")
    with ZipFile(BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > 256 or len({entry.filename for entry in entries}) != len(entries):
            raise ValueError("Too many or duplicate ZIP entries")
        total_size = 0
        for entry in entries:
            if entry.orig_filename != entry.filename or not _allowed_workbook_part(entry.filename):
                raise ValueError("Unsupported workbook ZIP entry")
            total_size += entry.file_size
            if (entry.file_size > 16 * 1024 * 1024 or total_size > 32 * 1024 * 1024
                    or entry.file_size > max(entry.compress_size, 1) * 200
                    or entry.flag_bits & 1):
                raise ValueError("Unsafe workbook expansion")
            if entry.filename.endswith(".xml"):
                xml = archive.read(entry)
                if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                    raise ValueError("XML entities are not supported")
        strings = _shared_strings(archive)
        if len(strings) > 100000 or any(len(value) > 10000 for value in strings):
            raise ValueError("Shared strings exceed limits")
        paths = sorted((name for name in archive.namelist() if name.startswith("xl/worksheets/") and name.endswith(".xml")), key=lambda name: int("".join(char for char in name if char.isdigit()) or 0))
        if len(paths) < 4 or len(paths) > 16:
            raise ValueError("Workbook must contain four worksheets")
        sheets = []
        for path in paths[:4]:
            root = _parse_xml(archive.read(path)); rows = []
            for row in root.findall("{*}sheetData/{*}row"):
                if len(rows) >= 10000:
                    raise ValueError("Too many worksheet rows")
                rows.append(_row_values(row, strings))
            sheets.append(rows)
    return sheets
