import pytest
from pydantic import ValidationError
from backend.config_routes import QuoteRequest


@pytest.mark.parametrize('field,limit', [('title', 200), ('customer_name', 200),
                                        ('customer_email', 200), ('customer_phone', 80),
                                        ('customer_address', 500)])
def test_quote_text_limits(field, limit):
    assert getattr(QuoteRequest(**{field: 'x' * limit}), field) == 'x' * limit
    with pytest.raises(ValidationError):
        QuoteRequest(**{field: 'x' * (limit + 1)})


@pytest.mark.parametrize('field', ['config_id', 'quote_id', 'source_share_id', 'source_inquiry_id'])
def test_quote_identifier_limits(field):
    assert getattr(QuoteRequest(**{field: 'x' * 100}), field) == 'x' * 100
    with pytest.raises(ValidationError):
        QuoteRequest(**{field: 'x' * 101})


@pytest.mark.parametrize('item', [None, 1, 'item', ['item']])
def test_quote_lines_must_be_objects(item):
    with pytest.raises(ValidationError):
        QuoteRequest(items=[item])


@pytest.mark.parametrize('value', [float('inf'), float('-inf'), float('nan')])
def test_nonfinite_nested_values_rejected(value):
    with pytest.raises(ValidationError):
        QuoteRequest(items=[{'kind': 'tool', 'price': value}])
    with pytest.raises(ValidationError):
        QuoteRequest(total_price=str(value))
