import pytest
from backend.catalog_identity import strip_redundant_catalog_code


@pytest.mark.parametrize('name,expected', [
    ('BTK-1016\r\nInjector\nTest\tKit', 'Injector Test Kit'),
    ('  喷油器\r\n测试\n套件  ', '喷油器 测试 套件'),
    ('Injector Test Kit', 'Injector Test Kit'),
])
def test_name_whitespace_is_normalized(name, expected):
    assert strip_redundant_catalog_code(name, 'BTK-1016') == expected
