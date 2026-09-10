import pytest
from pydantic import ValidationError
from backend.admin_routes import ConfigOptionCreateRequest, ConfigOptionUpdateRequest


@pytest.mark.parametrize('field,limit', [('code', 200), ('name', 300), ('name_en', 300),
    ('description', 10000), ('description_en', 10000), ('notes', 5000)])
@pytest.mark.parametrize('model', [ConfigOptionCreateRequest, ConfigOptionUpdateRequest])
def test_legacy_catalog_text_bounds(model, field, limit):
    values = dict(category_id='test', code='TEST-1', name='Test') if model is ConfigOptionCreateRequest else {}
    values[field] = 'x' * limit
    model(**values)
    values[field] += 'x'
    with pytest.raises(ValidationError):
        model(**values)


@pytest.mark.parametrize('field', ['price', 'price_usd'])
@pytest.mark.parametrize('value', [-1, 9223372036854775808])
def test_legacy_price_rejected_before_sqlite(field, value):
    with pytest.raises(ValidationError):
        ConfigOptionUpdateRequest(**{field: value})


def test_partial_update_preserves_omitted_values():
    assert ConfigOptionUpdateRequest(version=1).model_dump(exclude_unset=True) == {'version': 1}


@pytest.mark.parametrize('field', ['version', 'sort_order'])
def test_integer_bindings_fit_sqlite(field):
    with pytest.raises(ValidationError):
        ConfigOptionUpdateRequest(**{field: 9223372036854775808})
