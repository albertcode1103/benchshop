"""Generate isolated PDF QA samples; never reads or writes business records."""
from pathlib import Path
from io import BytesIO
from pypdf import PdfReader
from backend.pdf_service import commerce_bundle_pdf, quote_pdf
from backend.pdf_identity import pdf_identity

out = Path("tmp/pdf-identity")
out.mkdir(parents=True, exist_ok=True)
for lang in ("zh", "en"):
    name = "测试设备" if lang == "zh" else "Test Bench"
    entries = [{"item_type":"device_config", "quantity":1,"snapshot":{"product":{"name":"BOTEN CR1016","title_name":name},"color":{"label":"Red"},"categories":[{"id":"kit","name":"测试套件" if lang == "zh" else "Test Kits","options":[{"code":"BTK-1016","name":name}]}]}}]
    for kind, number in (("share","123456"),("inquiry","BTI-20260911-0001"),("quote","BTQ-20260911-0001")):
        code = pdf_identity(kind, number)
        if kind == "quote":
            content = quote_pdf({"quote_number":number,"language":lang,"currency":"CNY","created_at":"2026-09-11 09:00:00","customer_name":"QA","items":[{"kind":"product","device_key":"d1","code":"CR1016","name":name,"quantity":1,"price":10000}],"total_price":10000})
        else:
            content = commerce_bundle_pdf(entries,{"display_name":"QA"},lang,document_kind="inquiry" if kind == "inquiry" else "configuration",document_code=code,note="QA",created_at="2026-09-11 09:00:00")
        assert code in "\n".join(page.extract_text() for page in PdfReader(BytesIO(content)).pages)
        (out / f"{code}-{lang}.pdf").write_bytes(content)
print("Six PDF samples generated; all page document identities verified")
