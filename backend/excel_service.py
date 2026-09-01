"""Dependency-free XLSX export for catalog maintenance templates."""
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape
from xml.etree import ElementTree as ET

def _sheet(rows):
    cells=[]
    for r, row in enumerate(rows,1):
        vals=[]
        for c, value in enumerate(row,1):
            col=""
            n=c
            while n:
                n, rem=divmod(n-1,26); col=chr(65+rem)+col
            text="" if value is None else str(value)
            vals.append(f'<c r="{col}{r}" t="inlineStr"><is><t>{escape(text)}</t></is></c>')
        cells.append(f'<row r="{r}">'+''.join(vals)+'</row>')
    return '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+''.join(cells)+'</sheetData></worksheet>'

def catalog_template(products, categories):
    sheets=[("设备目录", [["设备型号","中文名称","英文名称","人民币参考价","美元参考价","启用"]]+[[p["id"],p["name"],p.get("name_en",""),p.get("base_price",0),p.get("price_usd",0),p.get("enabled",True)] for p in products]), ("配置目录", [["配置编号","分类编号","中文名称","英文名称","中文描述","英文描述","备注","人民币价格","美元价格","启用"]]+[[o["id"],c["id"],o["name"],o.get("name_en",""),o.get("description",""),o.get("description_en",""),o.get("notes",""),o.get("price",0),o.get("price_usd",0),o.get("enabled",True)] for c in categories for o in c.get("options",[])]), ("电机价格", [["设备型号","电机配置编号","人民币基础价","美元基础价"]]), ("设备参数", [["设备型号","参数ID","中文项目","英文项目","中文数据","英文数据","排序"]])]
    out=BytesIO()
    with ZipFile(out,"w",ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet3.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet4.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr("xl/workbook.xml",'<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>' for i,(n,_) in enumerate(sheets,1))+'</sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,5))+'</Relationships>')
        for i,(_, rows) in enumerate(sheets,1): z.writestr(f"xl/worksheets/sheet{i}.xml",_sheet(rows))
    return out.getvalue()

def parse_xlsx(data):
    """Read the simple inline-string workbook emitted by catalog_template."""
    result=[]
    with ZipFile(BytesIO(data)) as z:
        for i in range(1,5):
            root=ET.fromstring(z.read(f"xl/worksheets/sheet{i}.xml")); rows=[]
            for row in root.findall("{*}sheetData/{*}row"):
                rows.append(["".join(cell.itertext()) for cell in row.findall("{*}c")])
            result.append(rows)
    return result
