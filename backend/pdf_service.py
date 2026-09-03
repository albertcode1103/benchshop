"""Cross-platform PDF generation for configurations and quotations."""

import os
import hashlib
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase import pdfdoc
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle


# Some Python 3.8/OpenSSL builds do not accept hashlib's newer
# ``usedforsecurity`` keyword, while ReportLab passes it when creating a PDF.
try:
    hashlib.md5(usedforsecurity=False)
except TypeError:
    pdfdoc.md5 = lambda value=b"", **_: hashlib.md5(value)


BRAND_BLUE = colors.HexColor("#183B56")
ACCENT_BLUE = colors.HexColor("#2E75B6")
LIGHT_BLUE = colors.HexColor("#EAF2F8")
LIGHT_GRAY = colors.HexColor("#F4F6F7")
TEXT_GRAY = colors.HexColor("#566573")


def _register_font() -> str:
    bundled_font = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "harmonyos-sans" / "HarmonyOS_Sans_SC.ttf"
    candidates = [
        os.getenv("BOTEN_PDF_FONT_PATH", "").strip(),
        str(bundled_font),
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont("BotenCJK", candidate, subfontIndex=0))
            return "BotenCJK"
        except Exception:
            continue
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return "STSong-Light"


FONT_NAME = _register_font()


def _paragraph(value: Any, style: ParagraphStyle) -> Paragraph:
    text = escape(str(value or "")).replace("\n", "<br/>")
    return Paragraph(text or "-", style)


def _option_detail_paragraph(option: Dict[str, Any], style: ParagraphStyle) -> Paragraph:
    parts = [escape(str(option.get("name") or "-"))]
    description = str(option.get("description") or "").strip()
    special_note = str(option.get("special_note") or "").strip()
    if description:
        parts.append(escape(description).replace("\n", "<br/>"))
    if special_note:
        parts.append("<b>{}</b>".format(escape(special_note).replace("\n", "<br/>")))
    return Paragraph("<br/>".join(parts), style)


def _styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("BotenTitle", parent=base["Title"], fontName=FONT_NAME, fontSize=20, leading=27, textColor=BRAND_BLUE, alignment=TA_CENTER, spaceAfter=6 * mm),
        "meta": ParagraphStyle("BotenMeta", parent=base["BodyText"], fontName=FONT_NAME, fontSize=8.5, leading=12, textColor=TEXT_GRAY),
        "section": ParagraphStyle("BotenSection", parent=base["Heading2"], fontName=FONT_NAME, fontSize=12, leading=16, textColor=BRAND_BLUE, spaceBefore=4 * mm, spaceAfter=2 * mm),
        "body": ParagraphStyle("BotenBody", parent=base["BodyText"], fontName=FONT_NAME, fontSize=9, leading=13, textColor=colors.HexColor("#17202A")),
        "header": ParagraphStyle("BotenHeader", parent=base["BodyText"], fontName=FONT_NAME, fontSize=9, leading=13, textColor=colors.white),
        "small": ParagraphStyle("BotenSmall", parent=base["BodyText"], fontName=FONT_NAME, fontSize=7.5, leading=10.5, textColor=TEXT_GRAY),
        "money": ParagraphStyle("BotenMoney", parent=base["BodyText"], fontName=FONT_NAME, fontSize=9, leading=13, alignment=TA_RIGHT),
        "total": ParagraphStyle("BotenTotal", parent=base["Heading2"], fontName=FONT_NAME, fontSize=14, leading=18, alignment=TA_RIGHT, textColor=BRAND_BLUE),
    }


class _BotenDocument(BaseDocTemplate):
    def __init__(self, stream: BytesIO, title: str):
        super().__init__(stream, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=18 * mm, bottomMargin=17 * mm, title=title, author="BOTEN")
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="content")
        self.addPageTemplates(PageTemplate(id="main", frames=[frame], onPage=self._draw_page))

    def _draw_page(self, canvas, document) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D6E4ED"))
        canvas.line(self.leftMargin, 12 * mm, A4[0] - self.rightMargin, 12 * mm)
        canvas.setFont(FONT_NAME, 7.5)
        canvas.setFillColor(TEXT_GRAY)
        canvas.drawString(self.leftMargin, 7.5 * mm, "BOTEN Diesel Test Bench")
        canvas.drawRightString(A4[0] - self.rightMargin, 7.5 * mm, "Page {}".format(document.page))
        canvas.restoreState()


def _build_pdf(title: str, story: Iterable[Any]) -> bytes:
    stream = BytesIO()
    _BotenDocument(stream, title).build(list(story))
    return stream.getvalue()


def _header(title: str, reference: str = "") -> List[Any]:
    styles = _styles()
    story: List[Any] = [_paragraph(title, styles["title"])]
    if reference:
        meta = Table([[_paragraph("BOTEN", styles["meta"]), _paragraph(reference, styles["meta"])]], colWidths=[85 * mm, 85 * mm])
        meta.setStyle(TableStyle([("ALIGN", (1, 0), (1, 0), "RIGHT"), ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm), ("LINEBELOW", (0, 0), (-1, -1), 0.8, ACCENT_BLUE)]))
        story.append(meta)
    return story


def configuration_pdf(snapshot: Dict[str, Any], title: str = "设备配置清单", reference: str = "") -> bytes:
    styles = _styles()
    product = snapshot.get("product") or {}
    product_name = " ".join(part for part in [str(product.get("name") or "").strip(), str(product.get("title_name") or "").strip()] if part)
    story = _header(title, reference)
    story.extend([
        _paragraph("设备 / Device", styles["section"]),
        _summary_table([
            ("型号与名称", product_name or product.get("id") or "-"),
            ("外观颜色", (snapshot.get("color") or {}).get("label") or (snapshot.get("color") or {}).get("code") or "-"),
        ], styles),
        _paragraph("已选配置 / Selected Options", styles["section"]),
    ])
    rows: List[List[Any]] = [[_paragraph("类别", styles["header"]), _paragraph("编号", styles["header"]), _paragraph("名称与说明", styles["header"])]]
    for category in snapshot.get("categories") or []:
        for option in category.get("options") or []:
            rows.append([_paragraph(category.get("name") or category.get("id"), styles["body"]), _paragraph(option.get("code") or option.get("id"), styles["body"]), _option_detail_paragraph(option, styles["body"])])
    if len(rows) == 1:
        rows.append([_paragraph("-", styles["body"]), _paragraph("-", styles["body"]), _paragraph("未选择附加配置", styles["body"])])
    table = Table(rows, colWidths=[34 * mm, 35 * mm, 101 * mm], repeatRows=1, hAlign="LEFT")
    table.setStyle(_table_style())
    story.append(table)
    return _build_pdf(title, story)


def quote_pdf(quote: Dict[str, Any]) -> bytes:
    styles = _styles()
    currency = quote.get("currency") if quote.get("currency") in ("CNY", "USD") else "CNY"
    story = _header(str(quote.get("title") or "配置报价单"), "报价编号 / Quote: {}".format(str(quote.get("id") or "")[:8]))
    story.extend([_paragraph("币种 / Currency: {}".format(currency), styles["meta"]), Spacer(1, 5 * mm)])
    rows: List[List[Any]] = [[_paragraph("项目", styles["header"]), _paragraph("数量", styles["header"]), _paragraph("单价", styles["header"]), _paragraph("小计", styles["header"])]]
    for item in quote.get("items") or []:
        quantity = max(0, int(item.get("quantity") or 0))
        price = max(0.0, float(item.get("price") or 0))
        label = " ".join(part for part in (str(item.get("code") or "").strip(), str(item.get("name") or "").strip()) if part) or "-"
        rows.append([_paragraph(label, styles["body"]), _paragraph(quantity, styles["money"]), _paragraph("{} {:,.2f}".format(currency, price), styles["money"]), _paragraph("{} {:,.2f}".format(currency, price * quantity), styles["money"])])
    if len(rows) == 1:
        rows.append([_paragraph("-", styles["body"]), _paragraph("0", styles["money"]), _paragraph("{} 0.00".format(currency), styles["money"]), _paragraph("{} 0.00".format(currency), styles["money"])])
    table = Table(rows, colWidths=[94 * mm, 18 * mm, 29 * mm, 29 * mm], repeatRows=1, hAlign="LEFT")
    table.setStyle(_table_style(right_columns=(1, 2, 3)))
    story.extend([table, Spacer(1, 6 * mm), _paragraph("总计 / Total: {} {:,.2f}".format(currency, float(quote.get("total_price") or 0)), styles["total"])])
    return _build_pdf(str(quote.get("title") or "配置报价单"), story)


def _summary_table(items: Iterable[Any], styles: Dict[str, ParagraphStyle]) -> Table:
    rows = [[_paragraph(label, styles["small"]), _paragraph(value, styles["body"])] for label, value in items]
    table = Table(rows, colWidths=[34 * mm, 136 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D5DEE5")), ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D5DEE5")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return table


def _table_style(right_columns=()) -> TableStyle:
    commands = [("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7D2D9")), ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D9E0E5")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]
    for column in right_columns:
        commands.append(("ALIGN", (column, 1), (column, -1), "RIGHT"))
    return TableStyle(commands)
