from backend.quote_repository import _normalize_quote_items
from backend.config_routes import QuoteRequest
from pydantic import ValidationError
import pytest


def test_quote_request_rejects_unknown_item_fields():
    with pytest.raises(ValidationError, match='不支持的字段'):
        QuoteRequest(items=[{'name': 'Device', 'unexpected_snapshot': {'payload': 'x'}}])


def test_quote_request_preserves_known_fields():
    item = {'kind': 'product', 'name': 'Device', 'quantity': 2, 'price': 12.34,
            'device_specifications': [{'key': 'color', 'label': 'Color', 'value': 'Red'}]}
    assert QuoteRequest(items=[item]).items == [item]


@pytest.mark.parametrize('field,value', [
    ('device_specifications', [{'key': 'color', 'value': 'Red', 'extra': 'x'}]),
    ('device_specifications', [{'value': {'nested': 'payload'}}]),
    ('device_specifications', [{'key': 'x' * 101}]),
    ('device_specifications', 'not a list'),
    ('availability_details', [{'unexpected': 'object'}]),
    ('availability_details', ['x' * 1001]),
    ('availability_details', 'not a list'),
])
def test_quote_request_rejects_invalid_nested_details(field, value):
    with pytest.raises(ValidationError):
        QuoteRequest(items=[{'name': 'Device', field: value}])


def test_quote_request_preserves_availability_identifiers():
    item = {'kind': 'product', 'availability_details': ['cr1016', 'CAPTURE_STATUS_UNAVAILABLE']}
    assert QuoteRequest(items=[item]).items == [item]


def test_quote_normalization_drops_unknown_fields_without_changing_amounts():
    original = {
        'kind': 'product', 'source_id': 'cr1016', 'name': 'Device',
        'quantity': 2, 'price': 12.34, 'unexpected_snapshot': {'payload': 'secret'},
        'category_label': 'Configuration', 'category_sort_order': 3,
        'device_specifications': [{'key': 'color', 'label': 'Color', 'value': 'Red'}],
    }
    normalized = _normalize_quote_items([original])[0]
    assert 'unexpected_snapshot' not in normalized
    assert 'unexpected_snapshot' in original
    assert normalized['quantity'] * normalized['price'] == 24.68
    for field in ('source_id', 'name', 'category_label', 'category_sort_order', 'device_specifications'):
        assert normalized[field] == original[field]
