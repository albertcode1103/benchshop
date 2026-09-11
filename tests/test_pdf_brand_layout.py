"""Isolated export layout regression; never touches business records."""
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from pypdf import PdfReader

from backend import pdf_service as pdf


@pytest.mark.parametrize("language", ["zh", "en"])
@pytest.mark.parametrize("kind", ["configuration", "inquiry", "quote"])
def test_unified_brand_layout(language, kind):
    code = {"configuration": "ShareBench-BOTEN123456", "inquiry": "RFQ-BOTEN20260911-12345", "quote": "QUOTA-BOTEN20260911-12345"}[kind]
    items = [{"kind": "tool", "code": f"QA-{i:03}", "name": "测试工具" if language == "zh" else "Service tool", "quantity": 1, "price": 10} for i in range(65)]
    if kind == "quote":
        content = pdf.quote_pdf({"quote_number": "BTQ-20260911-12345", "language": language, "created_at": "2026-09-11 09:00:00", "customer_name": "QA", "items": items, "currency": "CNY", "total_price": 650})
    else:
        entries = [{"item_type": "tool", "quantity": 1, "snapshot": item} for item in items]
        content = pdf.commerce_bundle_pdf(entries, {"display_name": "QA"}, language, document_kind=kind, document_code=code, created_at="2026-09-11 09:00:00", is_share=kind == "configuration")
    out = Path("tmp/pdfs/brand-layout")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{kind}-{language}.pdf").write_bytes(content)
    reader = PdfReader(BytesIO(content))
    assert len(reader.pages) >= 2
    first_text = reader.pages[0].extract_text()
    assert pdf.PDF_COPY[language][kind + "_title"] in first_text
    assert b"2 Tr" in reader.pages[0].get_contents().get_data()
    if kind == "configuration":
        assert ("分享人" if language == "zh" else "Shared by") in first_text
    else:
        assert "2026-09-11 17:00:00" in first_text
        assert ("分享人" if language == "zh" else "Shared by") not in first_text
    timestamps = set()
    for page in reader.pages:
        pieces = []
        def collect(text, cm, tm, font, size):
            if text.strip():
                pieces.append((text.strip(), cm[4] + tm[4], cm[5] + tm[5]))
        page.extract_text(visitor_text=collect)
        header = " ".join(text for text, x, y in pieces if y > float(page.mediabox.height) - 85)
        assert pdf.COMPANY_NAMES[language] in header
        assert pdf.COMPANY_NAMES["en" if language == "zh" else "zh"] not in header
        assert pdf.WEBSITE in header
        assert ("马塘路108号" if language == "zh" else "Matang Road") in header
        if language == "en":
            address_lines = [(text, y) for text, x, y in pieces if "No.108" in text or "Suzhou, Jiangsu" in text]
            assert len(address_lines) == 2
            assert address_lines[0][1] > address_lines[1][1]
        assert code not in header
        footer = [(text, x, y) for text, x, y in pieces if y < 35]
        assert any(text == code and x < 60 for text, x, y in footer)
        assert not any(pdf.WEBSITE in text for text, x, y in footer)
        assert len(page.images) >= 1
        timestamp = next(text for text, x, y in footer if x > 350)
        timestamps.add(timestamp)
    assert len(timestamps) == 1


def test_logo_failure_is_explicit(tmp_path):
    for path in (tmp_path / "missing.png", tmp_path / "invalid.png"):
        if path.name == "invalid.png":
            path.write_bytes(b"not an image")
        with patch.object(pdf, "LOGO_PATH", path), pytest.raises(pdf.AccountError) as failure:
            pdf.commerce_bundle_pdf([], {}, "en")
        assert failure.value.code == "PDF_LOGO_UNAVAILABLE"


def test_non_share_customer_heading_unchanged():
    content = pdf.commerce_bundle_pdf([], {"display_name": "QA"}, "en")
    text = PdfReader(BytesIO(content)).pages[0].extract_text()
    assert "Customer" in text and "Shared by" not in text


def test_long_header_reserves_additional_space():
    context = pdf.PdfDocumentContext(kind="configuration", language="en")
    normal = pdf._UnifiedDocument(BytesIO(), context)
    with patch.dict(pdf.COMPANY_ADDRESSES, en=pdf.COMPANY_ADDRESSES["en"] * 3):
        wrapped = pdf._UnifiedDocument(BytesIO(), context)
    assert wrapped.header_height > normal.header_height
    assert wrapped.topMargin > normal.topMargin
