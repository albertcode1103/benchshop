import pytest
from pydantic import ValidationError
from backend.admin_routes import ConfigCategoryCreateRequest, ConfigCategoryUpdateRequest


@pytest.mark.parametrize('model', [ConfigCategoryCreateRequest, ConfigCategoryUpdateRequest])
@pytest.mark.parametrize('field,limit', [('name', 200), ('name_en', 200), ('description', 5000), ('description_en', 5000)])
def test_category_text_limits(model, field, limit):
    values = {'name': 'Category', field: 'x' * limit}
    assert getattr(model(**values), field) == values[field]
    with pytest.raises(ValidationError):
        model(**{**values, field: 'x' * (limit + 1)})


def test_category_sort_and_partial_update():
    assert ConfigCategoryUpdateRequest().model_dump(exclude_unset=True) == {}
    assert ConfigCategoryUpdateRequest(sort_order=-1).sort_order == -1
    for value in (-2**63-1, 2**63):
        with pytest.raises(ValidationError):
            ConfigCategoryUpdateRequest(sort_order=value)
