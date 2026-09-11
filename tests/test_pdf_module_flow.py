from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader
from backend.pdf_service import quote_pdf


@pytest.mark.parametrize('language', ['zh', 'en'])
def test_final_accessory_group_uses_remaining_page_space(language):
    items = [dict(kind=kind, code=f'{prefix}-{i:02}', name='QA item', quantity=1, price=10)
             for kind, prefix, count in [('tool', 'TOOL', 12), ('accessory', 'ACC', 18)]
             for i in range(count)]
    content = quote_pdf(dict(quote_number='BTQ-20260911-0001', language=language,
                            customer_name='QA', currency='CNY', items=items))
    target = Path('tmp/pdfs/module-flow')
    target.mkdir(parents=True, exist_ok=True)
    (target / f'flow-{language}.pdf').write_bytes(content)
    pages = PdfReader(BytesIO(content)).pages
    assert len(pages) == 2
    assert 'TOOL-11' in pages[0].extract_text()
    assert 'ACC-00' in pages[0].extract_text()  # Previously moved the whole group.
    assert 'ACC-17' in pages[-1].extract_text()
    assert '300.00' in pages[-1].extract_text()
    assert '300.00' not in pages[0].extract_text()
