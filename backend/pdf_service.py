"""Cross-platform PDF generation for configurations and quotations."""

import os
import hashlib
from datetime import datetime
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
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle


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


PDF_COPY = {
    "zh": {
        "title": "设备配置清单", "customer": "客户", "email": "邮箱", "exported": "导出时间",
        "device": "设备", "device_info": "设备信息", "model": "设备型号", "name": "设备名称",
        "color": "外观颜色", "motor": "电机配置", "voltage": "电源配置", "selected": "已选配置",
        "channel": "通道配置", "number": "序号", "category": "类别", "code": "配置编号", "configuration": "配置名称", "note": "备注",
        "quantity": "数量", "unit_price": "参考单价", "base_price": "设备基础价格", "tools": "维修工具", "accessories": "设备附件",
        "price_pending": "价格待确认", "empty": "未选择附加配置", "page": "第 {current} / {total} 页",
        "quote_title": "报价单", "quote_item": "项目", "subtotal": "小计", "total": "合计", "currency": "货币",
    },
    "en": {
        "title": "Configuration List", "customer": "Customer", "email": "Email", "exported": "Exported At",
        "device": "Device", "device_info": "Device Information", "model": "Model", "name": "Device Name",
        "color": "Appearance", "motor": "Motor", "voltage": "Power Supply", "selected": "Selected Options",
        "channel": "Channels", "number": "No.", "category": "Category", "code": "Code", "configuration": "Configuration", "note": "Note",
        "quantity": "Qty", "unit_price": "Reference Price", "base_price": "Device Base Price", "tools": "Service Tools", "accessories": "Accessories",
        "price_pending": "Price Pending", "empty": "No additional options selected", "page": "Page {current} / {total}",
        "quote_title": "Quotation", "quote_item": "Item", "subtotal": "Subtotal", "total": "Total", "currency": "Currency",
    },
}


class _NumberedCanvas(pdf_canvas.Canvas):
    def __init__(self, *args, language: str = "zh", **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self._language = language

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            copy = PDF_COPY[self._language]
            self.setFont(FONT_NAME, 7.5)
            self.setFillColor(TEXT_GRAY)
            self.drawRightString(A4[0] - 15 * mm, 7.5 * mm, copy["page"].format(current=self._pageNumber, total=total))
            super().showPage()
        super().save()


class _BundleDocument(BaseDocTemplate):
    def __init__(self, stream: BytesIO, title: str, customer: Dict[str, Any], language: str, exported_at: str, reference: str = ""):
        super().__init__(stream, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=31 * mm, bottomMargin=17 * mm, title=title, author="BOTEN")
        self.customer = customer
        self.language = language
        self.exported_at = exported_at
        self.reference = reference
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="content")
        self.addPageTemplates(PageTemplate(id="bundle", frames=[frame], onPage=self._draw_page))

    def _draw_page(self, canvas, document) -> None:
        copy = PDF_COPY[self.language]
        canvas.saveState()
        canvas.setFillColor(BRAND_BLUE)
        canvas.setFont(FONT_NAME, 9)
        canvas.drawString(self.leftMargin, A4[1] - 12 * mm, "BOTEN DIESEL TEST BENCH")
        customer_name = str(self.customer.get("display_name") or self.customer.get("name") or "-")
        customer_email = str(self.customer.get("email") or self.customer.get("phone") or "-")
        metadata_styles = [
            ParagraphStyle("BundleMetaLeft", fontName=FONT_NAME, fontSize=7.2, leading=9, textColor=TEXT_GRAY),
            ParagraphStyle("BundleMetaCenter", fontName=FONT_NAME, fontSize=7.2, leading=9, textColor=TEXT_GRAY, alignment=TA_CENTER),
            ParagraphStyle("BundleMetaRight", fontName=FONT_NAME, fontSize=7.2, leading=9, textColor=TEXT_GRAY, alignment=TA_RIGHT),
        ]
        metadata = Table([[
            _paragraph("{}: {}".format(copy["customer"], customer_name), metadata_styles[0]),
            _paragraph("{}: {}".format(copy["email"], customer_email), metadata_styles[1]),
            _paragraph("{}: {}".format(copy["exported"], self.exported_at), metadata_styles[2]),
        ]], colWidths=[49 * mm, 64 * mm, 57 * mm])
        metadata.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        _, metadata_height = metadata.wrap(self.width, 10 * mm)
        metadata.drawOn(canvas, self.leftMargin, A4[1] - 15 * mm - metadata_height)
        canvas.setStrokeColor(colors.HexColor("#D6E4ED"))
        canvas.line(self.leftMargin, A4[1] - 25 * mm, A4[0] - self.rightMargin, A4[1] - 25 * mm)
        canvas.line(self.leftMargin, 12 * mm, A4[0] - self.rightMargin, 12 * mm)
        canvas.drawString(self.leftMargin, 7.5 * mm, "BOTEN DIESEL TEST BENCH")
        if self.reference:
            canvas.drawCentredString(A4[0] / 2, 7.5 * mm, self.reference)
        canvas.restoreState()


def _selected_single(snapshot: Dict[str, Any], category_id: str) -> str:
    category = next((item for item in snapshot.get("categories") or [] if item.get("id") == category_id), None)
    option = (category.get("options") or [None])[0] if category else None
    return str((option or {}).get("name") or "-")


def configuration_bundle_pdf(configs: List[Dict[str, Any]], customer: Dict[str, Any], lang: str = "zh", reference: str = "") -> bytes:
    language = "en" if lang == "en" else "zh"
    copy = PDF_COPY[language]
    styles = _styles()
    exported_at = datetime.now().astimezone().strftime("%b %d, %Y %H:%M" if language == "en" else "%Y年%m月%d日 %H:%M")
    story: List[Any] = [_paragraph(copy["title"], styles["title"])]

    for device_index, config in enumerate(configs, start=1):
        snapshot = config.get("snapshot") or {}
        product = snapshot.get("product") or {}
        color = snapshot.get("color") or {}
        heading = "{} {} · {}".format(copy["device"], device_index, product.get("name") or product.get("id") or "-")
        summary = _summary_table([
            (copy["model"], product.get("name") or product.get("id") or "-"),
            (copy["name"], product.get("title_name") or "-"),
            (copy["color"], color.get("label") or color.get("code") or "-"),
            (copy["motor"], _selected_single(snapshot, "motor")),
            (copy["voltage"], _selected_single(snapshot, "voltage")),
        ], styles)
        story.extend([KeepTogether([_paragraph(heading, styles["section"]), summary]), _paragraph(copy["selected"], styles["section"])])

        rows: List[List[Any]] = [[
            _paragraph(copy["number"], styles["header"]), _paragraph(copy["category"], styles["header"]),
            _paragraph(copy["code"], styles["header"]), _paragraph(copy["configuration"], styles["header"]),
            _paragraph(copy["note"], styles["header"]),
        ]]
        option_number = 0
        for category in snapshot.get("categories") or []:
            if category.get("id") in ("motor", "voltage"):
                continue
            for option in category.get("options") or []:
                option_number += 1
                rows.append([
                    _paragraph(option_number, styles["body"]), _paragraph(category.get("name") or category.get("id"), styles["body"]),
                    _paragraph(option.get("code") or option.get("id"), styles["body"]), _paragraph(option.get("name") or "-", styles["body"]),
                    _paragraph(option.get("special_note") or "-", styles["body"]),
                ])
        if len(rows) == 1:
            rows.append([_paragraph("-", styles["body"]), _paragraph("-", styles["body"]), _paragraph("-", styles["body"]), _paragraph(copy["empty"], styles["body"]), _paragraph("-", styles["body"])])
        table = Table(rows, colWidths=[12 * mm, 34 * mm, 30 * mm, 58 * mm, 36 * mm], repeatRows=1, hAlign="LEFT")
        table.setStyle(_table_style())
        story.append(table)
        if device_index < len(configs):
            # A spacer immediately before PageBreak can itself overflow the frame,
            # leaving the following device page without the expected page setup.
            story.append(PageBreak())

    stream = BytesIO()
    document = _BundleDocument(stream, copy["title"], customer, language, exported_at, reference)
    document.build(story, canvasmaker=lambda *args, **kwargs: _NumberedCanvas(*args, language=language, **kwargs))
    return stream.getvalue()


def _document_price(value: Any, currency: str, copy: Dict[str, str]) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0
    if amount <= 0:
        return copy["price_pending"]
    return "{} {:,.2f}".format(currency, amount)


def commerce_bundle_pdf(
    entries: List[Dict[str, Any]],
    customer: Dict[str, Any],
    lang: str = "zh",
    reference: str = "",
    *,
    include_prices: bool = False,
) -> bytes:
    """Render a mixed device/tool/accessory cart with immutable localized snapshots."""
    language = "en" if lang == "en" else "zh"
    currency = "USD" if language == "en" else "CNY"
    copy = PDF_COPY[language]
    styles = _styles()
    exported_at = datetime.now().astimezone().strftime("%b %d, %Y %H:%M" if language == "en" else "%Y年%m月%d日 %H:%M")
    story: List[Any] = [_paragraph(copy["title"], styles["title"])]
    devices = [entry for entry in entries if entry.get("item_type") == "device_config"]

    for device_index, entry in enumerate(devices, start=1):
        snapshot = entry.get("snapshot") or {}
        product = snapshot.get("product") or {}
        color = snapshot.get("color") or {}
        heading = "{} {} · {}".format(copy["device"], device_index, product.get("name") or product.get("id") or "-")
        summary = _summary_table(
            [
                (copy["model"], product.get("name") or product.get("id") or "-"),
                (copy["name"], product.get("title_name") or "-"),
                (copy["color"], color.get("label") or color.get("code") or "-"),
                (copy["motor"], _selected_single(snapshot, "motor")),
                (copy["voltage"], _selected_single(snapshot, "voltage")),
                (copy["channel"], _selected_single(snapshot, "channel")) if any(item.get("id") == "channel" for item in snapshot.get("categories") or []) else None,
            ],
            styles,
        )
        story.extend([KeepTogether([_paragraph(heading, styles["section"]), summary]), _paragraph(copy["selected"], styles["section"])])
        rows: List[List[Any]] = [[
            _paragraph(copy["number"], styles["header"]),
            _paragraph(copy["category"], styles["header"]),
            _paragraph(copy["code"], styles["header"]),
            _paragraph(copy["configuration"], styles["header"]),
            _paragraph(copy["quantity"], styles["header"]),
        ]]
        if include_prices:
            rows[0].append(_paragraph(copy["unit_price"], styles["header"]))
        option_number = 0
        for category in snapshot.get("categories") or []:
            if category.get("id") in ("motor", "voltage", "channel"):
                continue
            for option in category.get("options") or []:
                option_number += 1
                row = [
                    _paragraph(option_number, styles["body"]),
                    _paragraph(category.get("name") or category.get("id"), styles["body"]),
                    _paragraph(option.get("code") or option.get("id"), styles["body"]),
                    _paragraph(option.get("name") or "-", styles["body"]),
                    _paragraph("1", styles["money"]),
                ]
                if include_prices:
                    amount = option.get("price_usd") if currency == "USD" else option.get("price_cny", option.get("price"))
                    row.append(_paragraph(_document_price(amount, currency, copy), styles["money"]))
                rows.append(row)
        if len(rows) == 1:
            rows.append([
                _paragraph("-", styles["body"]), _paragraph("-", styles["body"]),
                _paragraph("-", styles["body"]), _paragraph(copy["empty"], styles["body"]),
                _paragraph("0", styles["money"]),
            ])
            if include_prices:
                rows[-1].append(_paragraph("-", styles["money"]))
        widths = [10 * mm, 34 * mm, 31 * mm, 75 * mm, 20 * mm]
        if include_prices:
            widths = [10 * mm, 30 * mm, 28 * mm, 57 * mm, 15 * mm, 30 * mm]
        table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(_table_style(right_columns=(4, 5) if include_prices else (4,)))
        story.append(table)
        if device_index < len(devices):
            story.append(PageBreak())

    has_previous_section = bool(devices)
    for item_type, title_key in (("tool", "tools"), ("accessory", "accessories")):
        items = [entry for entry in entries if entry.get("item_type") == item_type]
        if not items:
            continue
        if has_previous_section:
            story.append(PageBreak())
        story.append(_paragraph(copy[title_key], styles["section"]))
        rows = [[
            _paragraph(copy["number"], styles["header"]),
            _paragraph(copy["code"], styles["header"]),
            _paragraph(copy["configuration"], styles["header"]),
            _paragraph(copy["quantity"], styles["header"]),
        ]]
        if include_prices:
            rows[0].append(_paragraph(copy["unit_price"], styles["header"]))
        for index, entry in enumerate(items, start=1):
            snapshot = entry.get("snapshot") or {}
            row = [
                _paragraph(index, styles["body"]),
                _paragraph(snapshot.get("code") or "-", styles["body"]),
                _paragraph(snapshot.get("name") or "-", styles["body"]),
                _paragraph(entry.get("quantity") or snapshot.get("quantity") or 1, styles["money"]),
            ]
            if include_prices:
                amount = snapshot.get("price_usd") if currency == "USD" else snapshot.get("price_cny")
                row.append(_paragraph(_document_price(amount, currency, copy), styles["money"]))
            rows.append(row)
        widths = [12 * mm, 40 * mm, 98 * mm, 20 * mm]
        if include_prices:
            widths = [12 * mm, 36 * mm, 75 * mm, 17 * mm, 30 * mm]
        table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(_table_style(right_columns=(3, 4) if include_prices else (3,)))
        story.append(table)
        has_previous_section = True

    if not entries:
        story.append(_paragraph(copy["empty"], styles["body"]))
    stream = BytesIO()
    document = _BundleDocument(stream, copy["title"], customer, language, exported_at, reference)
    document.build(story, canvasmaker=lambda *args, **kwargs: _NumberedCanvas(*args, language=language, **kwargs))
    return stream.getvalue()


def quote_pdf(quote: Dict[str, Any]) -> bytes:
    language = "en" if quote.get("language") == "en" else "zh"
    copy = PDF_COPY[language]
    styles = _styles()
    currency = quote.get("currency") if quote.get("currency") in ("CNY", "USD") else "CNY"
    title = str(quote.get("title") or copy["quote_title"])
    exported_at = datetime.now().astimezone().strftime("%b %d, %Y %H:%M" if language == "en" else "%Y年%m月%d日 %H:%M")
    story: List[Any] = [
        _paragraph(title, styles["title"]),
        _paragraph("{}: {}".format(copy["currency"], currency), styles["meta"]),
        Spacer(1, 5 * mm),
    ]
    rows: List[List[Any]] = [[
        _paragraph(copy["number"], styles["header"]),
        _paragraph(copy["quote_item"], styles["header"]),
        _paragraph(copy["quantity"], styles["header"]),
        _paragraph(copy["unit_price"], styles["header"]),
        _paragraph(copy["subtotal"], styles["header"]),
    ]]
    for index, item in enumerate(quote.get("items") or [], start=1):
        quantity = max(0, int(item.get("quantity") or 0))
        price = max(0.0, float(item.get("price") or 0))
        context = str(item.get("device_label") or "").strip()
        label = " · ".join(part for part in (context, str(item.get("code") or "").strip(), str(item.get("name") or "").strip()) if part) or "-"
        rows.append([
            _paragraph(index, styles["body"]),
            _paragraph(label, styles["body"]),
            _paragraph(quantity, styles["money"]),
            _paragraph("{} {:,.2f}".format(currency, price), styles["money"]),
            _paragraph("{} {:,.2f}".format(currency, price * quantity), styles["money"]),
        ])
    if len(rows) == 1:
        rows.append([_paragraph("-", styles["body"]), _paragraph("-", styles["body"]), _paragraph("0", styles["money"]), _paragraph("{} 0.00".format(currency), styles["money"]), _paragraph("{} 0.00".format(currency), styles["money"])])
    table = Table(rows, colWidths=[11 * mm, 82 * mm, 18 * mm, 29 * mm, 30 * mm], repeatRows=1, hAlign="LEFT")
    table.setStyle(_table_style(right_columns=(2, 3, 4)))
    story.extend([table, Spacer(1, 6 * mm), _paragraph("{}: {} {:,.2f}".format(copy["total"], currency, float(quote.get("total_price") or 0)), styles["total"])])
    stream = BytesIO()
    customer = {"display_name": quote.get("customer_name") or "-", "email": quote.get("customer_email") or "-"}
    document = _BundleDocument(stream, title, customer, language, exported_at, "Quote: {}".format(str(quote.get("id") or "")[:8]))
    document.build(story, canvasmaker=lambda *args, **kwargs: _NumberedCanvas(*args, language=language, **kwargs))
    return stream.getvalue()


def _summary_table(items: Iterable[Any], styles: Dict[str, ParagraphStyle]) -> Table:
    rows = [[_paragraph(label, styles["small"]), _paragraph(value, styles["body"])] for item in items if item for label, value in [item]]
    table = Table(rows, colWidths=[34 * mm, 136 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D5DEE5")), ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D5DEE5")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return table


def _table_style(right_columns=()) -> TableStyle:
    commands = [("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7D2D9")), ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D9E0E5")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]
    for column in right_columns:
        commands.append(("ALIGN", (column, 1), (column, -1), "RIGHT"))
    return TableStyle(commands)
