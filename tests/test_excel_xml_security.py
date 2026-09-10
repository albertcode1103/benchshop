import pytest
from backend.excel_service import _parse_xml


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-16-le", "utf-16-be"])
def test_dtd_rejected_independently_of_encoding(encoding):
    declaration = "UTF-16" if encoding.startswith("utf-16") else "UTF-8"
    xml = '<?xml version="1.0" encoding="{}"?><!DOCTYPE a [<!ENTITY x "expanded">]><a>&x;</a>'.format(declaration)
    with pytest.raises(ValueError, match="document types"):
        _parse_xml(xml.encode(encoding))


def test_normal_unicode_xml_is_preserved():
    xml = '<?xml version="1.0" encoding="UTF-16"?><a>设备 &amp; 配置</a>'
    assert _parse_xml(xml.encode('utf-16')).text == '设备 & 配置'
