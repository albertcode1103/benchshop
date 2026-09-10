import pytest
from pydantic import ValidationError
from backend.admin_routes import MotorBasePriceRequest, ProductOptionOverrideRequest, ProductCreateRequest, ProductUpdateRequest


@pytest.mark.parametrize('model,field', [(MotorBasePriceRequest, 'base_price_cny'),
    (MotorBasePriceRequest, 'base_price_usd'), (ProductOptionOverrideRequest, 'price_override')])
@pytest.mark.parametrize('value', [-1, 2**63])
def test_product_prices_reject_negative_and_overflow(model, field, value):
    with pytest.raises(ValidationError):
        model(**{field: value})


def test_optional_override_preserves_clear_and_zero():
    assert ProductOptionOverrideRequest().price_override is None
    assert ProductOptionOverrideRequest(price_override=None).price_override is None
    assert ProductOptionOverrideRequest(price_override=0).price_override == 0
    assert MotorBasePriceRequest(base_price_cny=2**63-1).base_price_cny == 2**63-1


@pytest.mark.parametrize('model', [ProductCreateRequest, ProductUpdateRequest])
@pytest.mark.parametrize('field', ['base_price', 'price_usd'])
@pytest.mark.parametrize('value', [-1, 2**63])
def test_product_base_prices_are_bounded(model, field, value):
    with pytest.raises(ValidationError):
        model(id='test', name='Test', title_name='Test', **{field: value})


def test_product_order_allows_negative_but_not_overflow():
    assert ProductUpdateRequest(sort_order=-1).sort_order == -1
    assert ProductUpdateRequest().model_dump(exclude_unset=True) == {}
    for value in (-2**63-1, 2**63):
        with pytest.raises(ValidationError):
            ProductUpdateRequest(sort_order=value)
