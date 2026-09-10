from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import pytest
from backend.excel_service import catalog_template, parse_xlsx


def workbook_with_part(name, content=b''):
    output = BytesIO()
    with ZipFile(BytesIO(catalog_template([], []))) as source, ZipFile(output, 'w', ZIP_DEFLATED) as target:
        for entry in source.infolist():
            target.writestr(entry.filename, source.read(entry))
        target.writestr(name.replace('\\', '/'), content)
    data = output.getvalue()
    # Preserve malformed separators in both ZIP headers on Windows, whose
    # writer otherwise normalizes them before the reader can inspect them.
    if '\\' in name:
        data = data.replace(name.replace('\\', '/').encode(), name.encode())
    return data


@pytest.mark.parametrize('name', ['../payload.xml', '/xl/worksheets/sheet5.xml',
    'xl/worksheets/../payload.xml', 'xl\\worksheets\\sheet5.xml',
    'xl/vbaProject.bin', 'xl/embeddings/object.bin', 'payload.exe'])
def test_rejects_unexpected_zip_parts(name):
    with pytest.raises(ValueError, match='Unsupported workbook ZIP entry'):
        parse_xlsx(workbook_with_part(name))


@pytest.mark.parametrize('name', ['docProps/core.xml', 'docProps/app.xml',
    'xl/styles.xml', 'xl/theme/theme1.xml', '_rels/.rels'])
def test_accepts_standard_metadata(name):
    assert len(parse_xlsx(workbook_with_part(name, b'<root/>'))) == 4
