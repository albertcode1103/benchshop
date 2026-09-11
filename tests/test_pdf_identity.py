import pytest
from backend.pdf_identity import pdf_identity

@pytest.mark.parametrize("kind,number,expected", [
    ("share", "001234", "ShareBench-BOTEN001234"),
    ("inquiry", "BTI-20260911-0001", "RFQ-BOTEN20260911-01"),
    ("inquiry", "BTI-20260911-0100", "RFQ-BOTEN20260911-100"),
    ("quote", "BTQ-20260911-0001", "QUOTA-BOTEN20260911-0001"),
    ("quote", "BTQ-20260911-10000", "QUOTA-BOTEN20260911-10000"),
])
def test_identity(kind, number, expected):
    assert pdf_identity(kind, number) == expected

def test_missing_number_requires_repair():
    with pytest.raises(ValueError):
        pdf_identity("quote", "")
