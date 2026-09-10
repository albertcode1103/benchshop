import pytest
from pydantic import ValidationError
from backend.config_routes import (
    QuoteRequest, SaveConfigRequest, CartBatchRequest, ConfigBatchRequest,
    CurrentDeviceInquiryRequest,
)


@pytest.mark.parametrize('model,values', [
    (QuoteRequest, {}),
    (SaveConfigRequest, dict(product_id='test', color='Red', selections={})),
    (CartBatchRequest, dict(items=[])),
    (ConfigBatchRequest, dict(config_ids=[])),
    (CurrentDeviceInquiryRequest, dict(product_id='test', color='Red', idempotency_key='test-key-123')),
])
def test_unknown_top_level_field_rejected(model, values):
    model(**values)
    with pytest.raises(ValidationError) as failure:
        model(**values, unexpected_field='must not be ignored')
    assert any(error['type'] == 'extra_forbidden' for error in failure.value.errors())


def test_cart_reference_rejects_extra_fields():
    with pytest.raises(ValidationError):
        CartBatchRequest(items=[dict(item_type='device_config', id='test', extra='bad')])
