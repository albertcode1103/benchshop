"""Unified, cross-platform PDF generation for BOTEN business documents."""

import hashlib
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfdoc, pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import BaseDocTemplate, CondPageBreak, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle

from .catalog_identity import normalize_catalog_code, strip_redundant_catalog_code


try:
    hashlib.md5(usedforsecurity=False)
except TypeError:
    pdfdoc.md5 = lambda value=b"", **_: hashlib.md5(value)


LOGGER = logging.getLogger(__name__)
# PDF exports intentionally retain the original BOTEN blue document palette.
# The website can evolve independently without changing the appearance of
# already-established customer-facing documents.
BRAND_BLUE = colors.HexColor("#183B56")
ACCENT_BLUE = colors.HexColor("#2E75B6")
LIGHT_BLUE = colors.HexColor("#EAF2F8")
TEXT_MAIN = colors.HexColor("#1A1A1A")
TEXT_GRAY = colors.HexColor("#666666")
BORDER_GRAY = colors.HexColor("#E5E7EB")
LIGHT_GRAY = colors.HexColor("#F7F8FA")
COMPANY_NAME = "BOTEN TESTING EQUIPMENT SUZHOU CO., LTD."
WEBSITE = "www.boten-diesel.com"
PDF_TIMEZONE = ZoneInfo("Asia/Shanghai")
LOGO_PATH = Path(__file__).resolve().parent.parent / "tb" / "site" / "BOTEN.png"


def _register_font() -> str:
    bundled_font = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "harmonyos-sans" / "HarmonyOS_Sans_SC.ttf"
    candidates = [
        os.getenv("BOTEN_PDF_FONT_PATH", "").strip(), str(bundled_font),
        r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
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
PDF_COPY = {
    "zh": {
        "configuration_title": "配置清单", "inquiry_title": "询价单", "quote_title": "报价单",
        "customer_info": "客户信息", "salesperson_info": "报价人", "document_info": "文档信息",
        "name": "姓名", "email": "邮箱", "phone": "电话", "subject": "报价主题",
        "status": "状态", "created": "创建时间", "valid_until": "有效期", "currency": "报价货币",
        "note": "备注", "no_note": "无备注", "file_code": "文件编码", "generated": "生成时间",
        "device": "设备", "model": "设备型号", "device_name": "设备名称", "appearance": "外观颜色",
        "motor": "电机配置", "power": "电源配置", "channel": "通道配置",
        "base_price": "设备基础价格", "basic_configuration": "基础配置", "optional_configuration": "可选配置",
        "tools": "维修工具", "accessories": "设备附件", "other": "其他项目",
        "number": "序号", "item_name": "名称", "quantity": "数量", "unit_price": "单价",
        "subtotal": "小计", "group_subtotal": "分组小计", "total": "合计", "unavailable": "已失效",
        "empty": "暂无配置项目", "page": "第 {current} / {total} 页",
        "draft": "草稿", "sent": "已发送", "archived": "已归档",
    },
    "en": {
        "configuration_title": "Configuration List", "inquiry_title": "Inquiry", "quote_title": "Quotation",
        "customer_info": "Customer", "salesperson_info": "Prepared By", "document_info": "Document Information",
        "name": "Name", "email": "Email", "phone": "Phone", "subject": "Quotation Subject",
        "status": "Status", "created": "Created", "valid_until": "Valid Until", "currency": "Currency",
        "note": "Note", "no_note": "No note", "file_code": "Document Code", "generated": "Generated",
        "device": "Device", "model": "Model", "device_name": "Device Name", "appearance": "Appearance",
        "motor": "Motor", "power": "Power Supply", "channel": "Channels",
        "base_price": "Device Base Price", "basic_configuration": "Basic Configuration", "optional_configuration": "Optional Configuration",
        "tools": "Service Tools", "accessories": "Accessories", "other": "Other Items",
        "number": "No.", "item_name": "Name", "quantity": "Qty", "unit_price": "Unit Price",
        "subtotal": "Subtotal", "group_subtotal": "Group Subtotal", "total": "Total", "unavailable": "Unavailable",
        "empty": "No configuration items", "page": "Page {current} / {total}",
        "draft": "Draft", "sent": "Sent", "archived": "Archived",
    },
}


@dataclass
class PdfDocumentContext:
    kind: str
    language: str = "zh"
    code: str = ""
    customer: Optional[Dict[str, Any]] = None
    salesperson: Optional[Dict[str, Any]] = None
    subject: str = ""
    note: str = ""
    currency: str = ""
    status: str = ""
    created_at: str = ""
    valid_until: str = ""
    generated_at: str = ""
    extra_fields: Optional[List[Tuple[str, Any]]] = None

    def __post_init__(self) -> None:
        self.kind = self.kind if self.kind in ("configuration", "inquiry", "quote") else "configuration"
        self.language = "en" if self.language == "en" else "zh"
        self.customer = dict(self.customer or {})
        self.salesperson = dict(self.salesperson or {})
        self.extra_fields = list(self.extra_fields or [])
        if not self.generated_at:
            self.generated_at = pdf_generated_at()


def pdf_generated_at(moment: Optional[datetime] = None) -> str:
    current = moment or datetime.now(PDF_TIMEZONE)
    if current.tzinfo is None:
        current = current.replace(tzinfo=PDF_TIMEZONE)
    return current.astimezone(PDF_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


def temporary_configuration_code(moment: Optional[datetime] = None, token: str = "") -> str:
    current = moment or datetime.now(PDF_TIMEZONE)
    if current.tzinfo is None:
        current = current.replace(tzinfo=PDF_TIMEZONE)
    suffix = (token or uuid.uuid4().hex[:4]).upper()[:4]
    return "CFG-{}-{}".format(current.astimezone(PDF_TIMEZONE).strftime("%Y%m%d-%H%M%S"), suffix)


def _language(value: Any) -> str:
    return "en" if value == "en" else "zh"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _is_configured(value: Any) -> bool:
    text = _clean(value)
    return bool(text) and text.casefold() not in {"-", "none", "not configured", "unconfigured", "未配置", "无"}


def _safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def _positive_quantity(value: Any, fallback: int = 1) -> int:
    """Keep legacy missing quantities compatible, but never revive explicit invalid rows."""
    if value is None or str(value).strip() == "":
        return fallback
    return max(0, _safe_int(value, 0))


def _safe_money(value: Any) -> float:
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _paragraph(value: Any, style: ParagraphStyle, empty: str = "-") -> Paragraph:
    text = escape(_clean(value)).replace("\n", "<br/>")
    return Paragraph(text or escape(empty), style)


def _styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("BotenTitle", parent=base["Title"], fontName=FONT_NAME, fontSize=21, leading=27, textColor=TEXT_MAIN, alignment=TA_LEFT, spaceAfter=5 * mm),
        "card_title": ParagraphStyle("BotenCardTitle", parent=base["BodyText"], fontName=FONT_NAME, fontSize=8.2, leading=11, textColor=BRAND_BLUE),
        "card_label": ParagraphStyle("BotenCardLabel", parent=base["BodyText"], fontName=FONT_NAME, fontSize=7.5, leading=10, textColor=TEXT_GRAY),
        "card_value": ParagraphStyle("BotenCardValue", parent=base["BodyText"], fontName=FONT_NAME, fontSize=8.7, leading=12, textColor=TEXT_MAIN),
        "section": ParagraphStyle("BotenSection", parent=base["Heading2"], fontName=FONT_NAME, fontSize=12, leading=16, textColor=TEXT_MAIN, alignment=TA_LEFT),
        "subsection": ParagraphStyle("BotenSubsection", parent=base["Heading3"], fontName=FONT_NAME, fontSize=9, leading=12, textColor=BRAND_BLUE),
        "body": ParagraphStyle("BotenBody", parent=base["BodyText"], fontName=FONT_NAME, fontSize=8.5, leading=12, textColor=TEXT_MAIN),
        "header": ParagraphStyle("BotenHeader", parent=base["BodyText"], fontName=FONT_NAME, fontSize=8, leading=11, textColor=colors.white),
        "money": ParagraphStyle("BotenMoney", parent=base["BodyText"], fontName=FONT_NAME, fontSize=8.5, leading=12, textColor=TEXT_MAIN, alignment=TA_RIGHT),
        "total": ParagraphStyle("BotenTotal", parent=base["Heading2"], fontName=FONT_NAME, fontSize=14, leading=18, alignment=TA_RIGHT, textColor=BRAND_BLUE),
        "total_label": ParagraphStyle("BotenTotalLabel", parent=base["BodyText"], fontName=FONT_NAME, fontSize=10, leading=14, textColor=colors.white),
        "total_money": ParagraphStyle("BotenTotalMoney", parent=base["BodyText"], fontName=FONT_NAME, fontSize=11, leading=14, textColor=colors.white, alignment=TA_RIGHT),
    }


def _title_for(context: PdfDocumentContext) -> str:
    return PDF_COPY[context.language]["{}_title".format(context.kind)]


def _party_values(party: Dict[str, Any], copy: Dict[str, str]) -> List[Tuple[str, str]]:
    return [
        (copy["name"], _clean(party.get("display_name") or party.get("name"))),
        (copy["email"], _clean(party.get("email"))),
        (copy["phone"], _clean(party.get("phone"))),
    ]


def _info_card(title: str, items: Iterable[Tuple[str, Any]], styles: Dict[str, ParagraphStyle], width: float) -> Optional[Table]:
    visible = [(label, _clean(value)) for label, value in items if _clean(value)]
    if not visible:
        return None
    rows: List[List[Any]] = [[_paragraph(title, styles["card_title"], ""), ""]]
    for label, value in visible:
        rows.append([_paragraph(label, styles["card_label"], ""), _paragraph(value, styles["card_value"], "")])
    card = Table(rows, colWidths=[25 * mm, max(width - 25 * mm, 10 * mm)], hAlign="LEFT")
    card.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, ACCENT_BLUE), ("BOX", (0, 0), (-1, -1), 0.6, BORDER_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return card


def _card_row(left: Optional[Table], right: Optional[Table]) -> Optional[Table]:
    if not left and not right:
        return None
    if left and right:
        row = Table([[left, "", right]], colWidths=[82 * mm, 6 * mm, 82 * mm], hAlign="LEFT")
    else:
        row = Table([[left or right]], colWidths=[170 * mm], hAlign="LEFT")
    row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return row


def _note_card(title: str, value: str, styles: Dict[str, ParagraphStyle], width: float) -> Table:
    card = Table([
        [_paragraph(title, styles["card_title"], "")],
        [_paragraph(value, styles["card_value"], "")],
    ], colWidths=[width], hAlign="LEFT")
    card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, ACCENT_BLUE),
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return card


def _status_label(value: Any, language: str) -> str:
    text = _clean(value)
    return PDF_COPY[language].get(text, text)


def _intro_story(context: PdfDocumentContext, styles: Dict[str, ParagraphStyle]) -> List[Any]:
    copy = PDF_COPY[context.language]
    story: List[Any] = [_paragraph(_title_for(context), styles["title"])]
    customer_card = _info_card(copy["customer_info"], _party_values(context.customer or {}, copy), styles, 82 * mm)
    salesperson_card = _info_card(copy["salesperson_info"], _party_values(context.salesperson or {}, copy), styles, 82 * mm) if context.kind == "quote" else None
    party_row = _card_row(customer_card, salesperson_card)
    if party_row:
        story.extend([party_row, Spacer(1, 3 * mm)])
    details: List[Tuple[str, Any]] = []
    if context.kind == "quote":
        details.extend([(copy["subject"], context.subject), (copy["currency"], context.currency), (copy["status"], _status_label(context.status, context.language)), (copy["created"], context.created_at), (copy["valid_until"], context.valid_until)])
    elif context.kind == "inquiry":
        details.extend([(copy["status"], context.status), (copy["created"], context.created_at)])
    details.extend(context.extra_fields or [])
    detail_card = _info_card(copy["document_info"], details, styles, 170 * mm)
    if detail_card:
        story.extend([detail_card, Spacer(1, 3 * mm)])
    if context.kind == "inquiry":
        story.extend([_note_card(copy["note"], context.note or copy["no_note"], styles, 170 * mm), Spacer(1, 2 * mm)])
    return story


def _load_logo() -> Optional[ImageReader]:
    try:
        if not LOGO_PATH.is_file():
            raise FileNotFoundError(str(LOGO_PATH))
        return ImageReader(str(LOGO_PATH))
    except Exception as error:
        LOGGER.warning("BOTEN PDF logo could not be loaded: %s", error)
        return None


class _NumberedCanvas(pdf_canvas.Canvas):
    def __init__(self, *args, context: PdfDocumentContext, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states: List[Dict[str, Any]] = []
        self._context = context

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            copy = PDF_COPY[self._context.language]
            self.saveState()
            self.setFont(FONT_NAME, 7.2)
            self.setFillColor(TEXT_GRAY)
            self.drawCentredString(A4[0] / 2, 7.2 * mm, copy["page"].format(current=self._pageNumber, total=total))
            self.restoreState()
            super().showPage()
        super().save()


class _UnifiedDocument(BaseDocTemplate):
    def __init__(self, stream: BytesIO, context: PdfDocumentContext):
        super().__init__(stream, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=28 * mm, bottomMargin=20 * mm, title=_title_for(context), author="BOTEN")
        self.context = context
        self.logo = _load_logo()
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="content")
        self.addPageTemplates(PageTemplate(id="boten", frames=[frame], onPage=self._draw_page))

    def _draw_page(self, canvas, document) -> None:
        copy = PDF_COPY[self.context.language]
        canvas.saveState()
        logo_y = A4[1] - 18 * mm
        if self.logo:
            source_width, source_height = self.logo.getSize()
            scale = min((38 * mm) / source_width, (10 * mm) / source_height)
            canvas.drawImage(self.logo, self.leftMargin, logo_y, width=source_width * scale, height=source_height * scale, preserveAspectRatio=True, mask="auto")
        else:
            canvas.setFont(FONT_NAME, 13)
            canvas.setFillColor(BRAND_BLUE)
            canvas.drawString(self.leftMargin, logo_y + 2 * mm, "BOTEN")
        canvas.setFont(FONT_NAME, 7.5)
        canvas.setFillColor(TEXT_MAIN)
        canvas.drawRightString(A4[0] - self.rightMargin, A4[1] - 12.5 * mm, COMPANY_NAME)
        canvas.setStrokeColor(ACCENT_BLUE)
        canvas.setLineWidth(0.8)
        canvas.line(self.leftMargin, A4[1] - 22 * mm, A4[0] - self.rightMargin, A4[1] - 22 * mm)
        canvas.setStrokeColor(BORDER_GRAY)
        canvas.setLineWidth(0.6)
        canvas.line(self.leftMargin, 14 * mm, A4[0] - self.rightMargin, 14 * mm)
        canvas.setFont(FONT_NAME, 7.1)
        canvas.setFillColor(TEXT_GRAY)
        if self.context.code:
            canvas.drawString(self.leftMargin, 7.2 * mm, "{}: {}".format(copy["file_code"], self.context.code))
        canvas.drawRightString(A4[0] - self.rightMargin, 9 * mm, "{}: {}".format(copy["generated"], self.context.generated_at))
        canvas.drawRightString(A4[0] - self.rightMargin, 5.8 * mm, WEBSITE)
        canvas.restoreState()


def _build_document(context: PdfDocumentContext, story: Sequence[Any]) -> bytes:
    stream = BytesIO()
    document = _UnifiedDocument(stream, context)
    document.build(list(story), canvasmaker=lambda *args, **kwargs: _NumberedCanvas(*args, context=context, **kwargs))
    return stream.getvalue()


def _summary_table(items: Iterable[Tuple[str, Any]], styles: Dict[str, ParagraphStyle]) -> Optional[Table]:
    visible = [(label, _clean(value)) for label, value in items if _is_configured(value)]
    if not visible:
        return None
    rows = [[_paragraph(label, styles["card_label"], ""), _paragraph(value, styles["card_value"], "")] for label, value in visible]
    table = Table(rows, colWidths=[34 * mm, 136 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_GRAY), ("BOX", (0, 0), (-1, -1), 0.5, BORDER_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER_GRAY), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _table_style(right_columns: Sequence[int] = (), title_row: bool = False) -> TableStyle:
    header_row = 1 if title_row else 0
    commands: List[Tuple[Any, ...]] = [
        ("BACKGROUND", (0, header_row), (-1, header_row), BRAND_BLUE), ("TEXTCOLOR", (0, header_row), (-1, header_row), colors.white),
        ("ROWBACKGROUNDS", (0, header_row + 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_GRAY), ("INNERGRID", (0, header_row), (-1, -1), 0.3, BORDER_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if title_row:
        commands.extend([("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), BRAND_BLUE), ("LINEBELOW", (0, 0), (-1, 0), 0.8, ACCENT_BLUE)])
    for column in right_columns:
        commands.append(("ALIGN", (column, header_row + 1), (column, -1), "RIGHT"))
    return TableStyle(commands)


def _display_item_name(item: Dict[str, Any], language: str) -> str:
    raw_code = _clean(item.get("code") or item.get("id"))
    code = normalize_catalog_code(raw_code)
    name = strip_redundant_catalog_code(item.get("name") or item.get("display_name"), code, (raw_code,))
    label = "\n".join(part for part in (code, name) if part) or "-"
    availability = _clean(item.get("availability"))
    if availability and availability not in ("active", "available"):
        label = "{} ({})".format(label, PDF_COPY[language]["unavailable"])
    return label


def _sort_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 2147483647


def _sorted_categories(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    indexed = list(enumerate(snapshot.get("categories") or []))
    indexed.sort(key=lambda pair: (_sort_value(pair[1].get("sort_order")), pair[0]))
    return [category for _, category in indexed]


def _sorted_options(category: Dict[str, Any]) -> List[Dict[str, Any]]:
    indexed = list(enumerate(category.get("options") or []))
    indexed.sort(key=lambda pair: (_sort_value(pair[1].get("sort_order")), _clean(pair[1].get("code") or pair[1].get("id")), pair[0]))
    return [option for _, option in indexed]


def _selected_single(snapshot: Dict[str, Any], category_id: str) -> str:
    category = next((item for item in snapshot.get("categories") or [] if item.get("id") == category_id), None)
    option = (category.get("options") or [None])[0] if category else None
    return _clean((option or {}).get("name") or (option or {}).get("code"))


def _section_heading(text: str, styles: Dict[str, ParagraphStyle]) -> Table:
    table = Table([[_paragraph(text, styles["section"], "")]], colWidths=[170 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1, ACCENT_BLUE), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return table


def _item_table(title: str, items: Sequence[Dict[str, Any]], styles: Dict[str, ParagraphStyle], language: str, currency: str = "", include_prices: bool = False, start_index: int = 1, grand_total: Optional[float] = None) -> Tuple[Table, float]:
    copy = PDF_COPY[language]
    headers = [copy["number"], copy["item_name"], copy["quantity"]]
    widths = [14 * mm, 136 * mm, 20 * mm]
    right_columns = [2]
    if include_prices:
        headers.extend([copy["unit_price"], copy["subtotal"]])
        widths = [12 * mm, 88 * mm, 16 * mm, 27 * mm, 27 * mm]
        right_columns = [2, 3, 4]
    rows: List[List[Any]] = [[_paragraph(title, styles["subsection"], "")] + [""] * (len(headers) - 1)]
    rows.append([_paragraph(label, styles["header"], "") for label in headers])
    subtotal = 0.0
    visible_items = [item for item in items if _positive_quantity(item.get("quantity")) > 0]
    for offset, item in enumerate(visible_items):
        quantity = _positive_quantity(item.get("quantity"))
        row: List[Any] = [_paragraph(start_index + offset, styles["body"]), _paragraph(_display_item_name(item, language), styles["body"]), _paragraph(quantity, styles["money"])]
        if include_prices:
            price = _safe_money(item.get("price", item.get("quoted_price")))
            line_total = price * quantity
            subtotal += line_total
            row.extend([_paragraph("{} {:,.2f}".format(currency, price), styles["money"]), _paragraph("{} {:,.2f}".format(currency, line_total), styles["money"])])
        rows.append(row)
    if include_prices:
        rows.append(["", _paragraph(copy["group_subtotal"], styles["card_value"]), "", "", _paragraph("{} {:,.2f}".format(currency, subtotal), styles["money"])])
        if grand_total is not None:
            rows.append(["", _paragraph(copy["total"], styles["total_label"]), "", "", _paragraph("{} {:,.2f}".format(currency, grand_total), styles["total_money"])])
    table = Table(rows, colWidths=widths, repeatRows=2, hAlign="LEFT", splitByRow=1)
    table.setStyle(_table_style(right_columns=right_columns, title_row=True))
    if include_prices:
        subtotal_row = -2 if grand_total is not None else -1
        table.setStyle(TableStyle([("BACKGROUND", (0, subtotal_row), (-1, subtotal_row), LIGHT_BLUE), ("LINEABOVE", (0, subtotal_row), (-1, subtotal_row), 0.6, ACCENT_BLUE), ("SPAN", (1, subtotal_row), (3, subtotal_row))]))
        if grand_total is not None:
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, -1), (-1, -1), BRAND_BLUE),
                ("LINEABOVE", (0, -1), (-1, -1), 1, ACCENT_BLUE),
                ("SPAN", (1, -1), (3, -1)),
            ]))
    return table, subtotal


def _guarded_table(table: Table, keep_whole: bool) -> List[Any]:
    if not keep_whole:
        return [table]
    _, height = table.wrap(170 * mm, 250 * mm)
    return [CondPageBreak(min(height, 220 * mm)), table]


def _device_story(snapshot: Dict[str, Any], device_index: int, styles: Dict[str, ParagraphStyle], language: str) -> List[Any]:
    copy = PDF_COPY[language]
    product = snapshot.get("product") or {}
    color = snapshot.get("color") or {}
    model = _clean(product.get("name") or product.get("id"))
    name = _clean(product.get("title_name"))
    heading = "{} {} - {}".format(copy["device"], device_index, " - ".join(part for part in (model, name) if part) or "-")
    summary = _summary_table([(copy["model"], model), (copy["device_name"], name), (copy["appearance"], color.get("label") or color.get("code")), (copy["motor"], _selected_single(snapshot, "motor")), (copy["power"], _selected_single(snapshot, "voltage")), (copy["channel"], _selected_single(snapshot, "channel"))], styles)
    content: List[Any] = [CondPageBreak(35 * mm), _section_heading(heading, styles)]
    if summary:
        content.extend([summary, Spacer(1, 2 * mm)])
    for category in _sorted_categories(snapshot):
        if category.get("id") in {"motor", "voltage", "channel"}:
            continue
        options = [option for option in _sorted_options(category) if _positive_quantity(option.get("quantity")) > 0]
        if not options:
            continue
        title = _clean(category.get("name") or category.get("id")) or copy["optional_configuration"]
        normalized = [dict(option, quantity=_positive_quantity(option.get("quantity"))) for option in options]
        table, _ = _item_table(title, normalized, styles, language)
        content.extend([table, Spacer(1, 2 * mm)])
    return content


def _canonical_entries(entries: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ranks = {"device_config": 0, "tool": 1, "accessory": 2}
    indexed = list(enumerate(entries))
    def key(pair: Tuple[int, Dict[str, Any]]) -> Tuple[Any, ...]:
        index, entry = pair
        item_type = _clean(entry.get("item_type"))
        snapshot = entry.get("snapshot") or {}
        if item_type == "device_config":
            return (0, _sort_value(entry.get("sort_order", index)), index)
        return (ranks.get(item_type, 3), _sort_value(snapshot.get("category_sort_order", snapshot.get("catalog_category_sort_order"))), _sort_value(snapshot.get("sort_order", snapshot.get("catalog_sort_order"))), _clean(snapshot.get("code") or entry.get("source_id")), _clean(snapshot.get("name") or entry.get("display_name")), index)
    indexed.sort(key=key)
    return [dict(entry) for _, entry in indexed]


def _aggregate_entries(entries: Sequence[Dict[str, Any]], item_type: str) -> List[Dict[str, Any]]:
    aggregated: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        if _clean(entry.get("item_type")) != item_type:
            continue
        snapshot = dict(entry.get("snapshot") or {})
        identity = _clean(entry.get("source_id") or snapshot.get("id") or snapshot.get("code") or snapshot.get("name"))
        key = identity.casefold() or uuid.uuid4().hex
        quantity = _positive_quantity(entry.get("quantity", snapshot.get("quantity")))
        if quantity <= 0:
            continue
        if key in aggregated:
            aggregated[key]["quantity"] += quantity
        else:
            snapshot["quantity"] = quantity
            aggregated[key] = snapshot
    return list(aggregated.values())


def _commerce_story(entries: Sequence[Dict[str, Any]], context: PdfDocumentContext) -> List[Any]:
    styles = _styles()
    copy = PDF_COPY[context.language]
    story = _intro_story(context, styles)
    canonical = _canonical_entries(entries)
    devices = [entry for entry in canonical if entry.get("item_type") == "device_config" and _positive_quantity(entry.get("quantity")) > 0]
    for index, entry in enumerate(devices, start=1):
        story.extend(_device_story(entry.get("snapshot") or {}, index, styles, context.language))
    for item_type, title_key in (("tool", "tools"), ("accessory", "accessories")):
        items = _aggregate_entries(canonical, item_type)
        if not items:
            continue
        story.append(CondPageBreak(30 * mm))
        table, _ = _item_table(copy[title_key], items, styles, context.language)
        story.extend([table, Spacer(1, 2 * mm)])
    unknown = []
    for entry in canonical:
        if entry.get("item_type") in ("device_config", "tool", "accessory"):
            continue
        item = dict(entry.get("snapshot") or {})
        item.setdefault("name", entry.get("display_name") or entry.get("source_id") or copy["other"])
        item["quantity"] = _positive_quantity(entry.get("quantity"))
        if item["quantity"] <= 0:
            continue
        item["availability"] = "snapshot_only"
        unknown.append(item)
    if unknown:
        story.append(CondPageBreak(30 * mm))
        table, _ = _item_table(copy["other"], unknown, styles, context.language)
        story.append(table)
    has_visible_content = bool(devices or _aggregate_entries(canonical, "tool") or _aggregate_entries(canonical, "accessory") or unknown)
    if not has_visible_content:
        story.append(_paragraph(copy["empty"], styles["body"]))
    return story


def _reference_code(reference: str) -> str:
    text = _clean(reference)
    return text.rsplit(":", 1)[-1].strip() if ":" in text else text


def configuration_pdf(snapshot: Dict[str, Any], title: str = "", reference: str = "", *, customer: Optional[Dict[str, Any]] = None, lang: str = "zh", document_code: str = "") -> bytes:
    context = PdfDocumentContext(kind="configuration", language=_language(lang), code=document_code or _reference_code(reference) or temporary_configuration_code(), customer=customer or {})
    entry = {"item_type": "device_config", "source_id": "current", "quantity": 1, "snapshot": snapshot}
    return _build_document(context, _commerce_story([entry], context))


def configuration_bundle_pdf(configs: List[Dict[str, Any]], customer: Dict[str, Any], lang: str = "zh", reference: str = "", *, document_code: str = "") -> bytes:
    entries = [{"item_type": "device_config", "source_id": config.get("id") or str(index), "sort_order": index, "quantity": 1, "snapshot": config.get("snapshot") or {}} for index, config in enumerate(configs)]
    context = PdfDocumentContext(kind="configuration", language=_language(lang), code=document_code or _reference_code(reference) or temporary_configuration_code(), customer=customer)
    return _build_document(context, _commerce_story(entries, context))


def commerce_bundle_pdf(entries: List[Dict[str, Any]], customer: Dict[str, Any], lang: str = "zh", reference: str = "", *, include_prices: bool = False, document_metadata: Any = None, document_kind: str = "configuration", document_code: str = "", note: str = "", status: str = "", created_at: str = "") -> bytes:
    """Render a canonical configuration or inquiry document without prices."""
    if include_prices:
        raise ValueError("Prices are only permitted in quotation PDFs")
    kind = "inquiry" if document_kind == "inquiry" else "configuration"
    context = PdfDocumentContext(kind=kind, language=_language(lang), code=document_code or _reference_code(reference) or temporary_configuration_code(), customer=customer, note=note, status=status, created_at=created_at, extra_fields=list(document_metadata or []))
    return _build_document(context, _commerce_story(entries, context))


def _quote_item_sort(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    indexed = list(enumerate(items))
    ranks = {"product": 0, "option": 1, "surcharge": 1, "tool": 2, "accessory": 3}
    indexed.sort(key=lambda pair: (0 if pair[1].get("kind") in ("product", "option", "surcharge") else ranks.get(_clean(pair[1].get("kind")), 4), _sort_value(pair[1].get("device_sequence")) if pair[1].get("kind") in ("product", "option", "surcharge") else _sort_value(pair[1].get("category_sort_order", pair[1].get("catalog_category_sort_order"))), 0 if pair[1].get("kind") == "product" else 1, _sort_value(pair[1].get("category_sort_order")), _sort_value(pair[1].get("sort_order", pair[1].get("catalog_sort_order"))), _clean(pair[1].get("code")), pair[0]))
    return [dict(item) for _, item in indexed]


def _aggregate_quote_items(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    aggregated: Dict[Tuple[str, float], Dict[str, Any]] = {}
    for item in items:
        quantity = _positive_quantity(item.get("quantity"))
        if quantity <= 0:
            continue
        identity = _clean(item.get("source_id") or item.get("id") or item.get("code") or item.get("name")).casefold()
        price = _safe_money(item.get("price", item.get("quoted_price")))
        key = (identity or uuid.uuid4().hex, price)
        if key in aggregated:
            aggregated[key]["quantity"] += quantity
        else:
            aggregated[key] = dict(item, quantity=quantity, price=price)
    return list(aggregated.values())


def _quote_groups(items: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    devices: Dict[str, Dict[str, Any]] = {}
    sequence_keys: Dict[int, str] = {}
    tools: List[Dict[str, Any]] = []
    accessories: List[Dict[str, Any]] = []
    other: List[Dict[str, Any]] = []
    invalid_device_keys = {
        _clean(item.get("device_key")) or "device-{}".format(max(1, _safe_int(item.get("device_sequence"), 1)))
        for item in items if _clean(item.get("kind")) == "product" and _positive_quantity(item.get("quantity")) <= 0
    }
    invalid_device_sequences = {
        _safe_int(item.get("device_sequence"))
        for item in items if _clean(item.get("kind")) == "product" and _positive_quantity(item.get("quantity")) <= 0
    }
    for item in _quote_item_sort(items):
        if _positive_quantity(item.get("quantity")) <= 0:
            continue
        kind = _clean(item.get("kind"))
        if kind == "product":
            sequence = max(1, _safe_int(item.get("device_sequence"), len(devices) + 1))
            key = _clean(item.get("device_key")) or "device-{}".format(sequence)
            devices[key] = {"sequence": sequence, "product": item, "options": []}
            sequence_keys[sequence] = key
        elif kind in ("option", "surcharge"):
            parent = _clean(item.get("parent_device_key")) or sequence_keys.get(_safe_int(item.get("device_sequence")), "")
            if parent in invalid_device_keys or _safe_int(item.get("device_sequence")) in invalid_device_sequences:
                continue
            if parent in devices:
                devices[parent]["options"].append(item)
            else:
                other.append(item)
        elif kind == "tool":
            tools.append(item)
        elif kind == "accessory":
            accessories.append(item)
        else:
            other.append(item)
    return sorted(devices.values(), key=lambda group: group["sequence"]), _aggregate_quote_items(tools), _aggregate_quote_items(accessories), other


def _quote_device_story(group: Dict[str, Any], index: int, styles: Dict[str, ParagraphStyle], context: PdfDocumentContext, grand_total: Optional[float] = None) -> Tuple[List[Any], float]:
    copy = PDF_COPY[context.language]
    product = group["product"]
    model = _clean(product.get("code") or product.get("model"))
    name = _clean(product.get("name"))
    heading = "{} {} - {}".format(copy["device"], index, " - ".join(part for part in (model, name) if part) or "-")
    summary_items = [(_clean(spec.get("label") or spec.get("key")), spec.get("value")) for spec in product.get("device_specifications") or [] if isinstance(spec, dict)]
    summary = _summary_table(summary_items, styles)
    story: List[Any] = [CondPageBreak(38 * mm), _section_heading(heading, styles)]
    if summary:
        story.extend([summary, Spacer(1, 2 * mm)])
    total = 0.0
    grouped_options: Dict[str, List[Dict[str, Any]]] = {}
    for item in group["options"]:
        category = _clean(item.get("category_name") or item.get("category_label")) or (copy["basic_configuration"] if item.get("kind") == "surcharge" else copy["optional_configuration"])
        grouped_options.setdefault(category, []).append(item)
    base_table, subtotal = _item_table(copy["base_price"], [product], styles, context.language, context.currency, True, grand_total=grand_total if not grouped_options else None)
    story.extend(_guarded_table(base_table, grand_total is not None and not grouped_options) + [Spacer(1, 2 * mm)])
    total += subtotal
    option_groups = list(grouped_options.items())
    for option_index, (category, options) in enumerate(option_groups):
        final_total = grand_total if option_index == len(option_groups) - 1 else None
        table, subtotal = _item_table(category, options, styles, context.language, context.currency, True, grand_total=final_total)
        story.extend(_guarded_table(table, final_total is not None) + [Spacer(1, 2 * mm)])
        total += subtotal
    return story, total


def quote_pdf(quote: Dict[str, Any]) -> bytes:
    language = _language(quote.get("language"))
    currency = quote.get("currency") if quote.get("currency") in ("CNY", "USD") else "CNY"
    quote_id = _clean(quote.get("id"))
    code = _clean(quote.get("quote_number")) or "DRAFT-{}".format((quote_id[:8] or uuid.uuid4().hex[:8]).upper())
    salesperson = quote.get("quoted_by") or quote.get("sender") or {"display_name": quote.get("display_name"), "email": quote.get("email"), "phone": quote.get("phone")}
    context = PdfDocumentContext(kind="quote", language=language, code=code, customer={"display_name": quote.get("customer_name"), "email": quote.get("customer_email"), "phone": quote.get("customer_phone")}, salesperson=salesperson, subject=_clean(quote.get("title")), currency=currency, status=_clean(quote.get("lifecycle_status") or "draft"), created_at=_clean(quote.get("created_at")), valid_until=_clean(quote.get("valid_until")))
    styles = _styles()
    copy = PDF_COPY[language]
    story = _intro_story(context, styles)
    devices, tools, accessories, other = _quote_groups(quote.get("items") or [])
    visible_quote_items = [line for group in devices for line in ([group["product"]] + group["options"])] + tools + accessories + other
    computed_total = sum(
        _safe_money(item.get("price", item.get("quoted_price"))) * _positive_quantity(item.get("quantity"))
        for item in visible_quote_items
    )
    declared_total = _safe_money(quote.get("total_price"))
    grand_total = computed_total if quote.get("items") else declared_total
    trailing_groups = [(items, title_key) for items, title_key in ((tools, "tools"), (accessories, "accessories"), (other, "other")) if items]
    for index, group in enumerate(devices, start=1):
        final_total = grand_total if index == len(devices) and not trailing_groups else None
        device_story, subtotal = _quote_device_story(group, index, styles, context, final_total)
        story.extend(device_story)
    for group_index, (items, title_key) in enumerate(trailing_groups):
        story.append(CondPageBreak(32 * mm))
        final_total = grand_total if group_index == len(trailing_groups) - 1 else None
        table, subtotal = _item_table(copy[title_key], items, styles, language, currency, True, grand_total=final_total)
        story.extend(_guarded_table(table, final_total is not None) + [Spacer(1, 2 * mm)])
    if not devices and not tools and not accessories and not other:
        story.append(_paragraph(copy["empty"], styles["body"]))
    return _build_document(context, story)
