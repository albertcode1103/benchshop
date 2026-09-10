import pytest
from backend.media_routes import validate_media_reference


@pytest.mark.parametrize("path", [None, "", "tb/tbpic/a.png", "/assets/a.webp",
                                  "https://example.com/image.png", "http://example.com/image"])
def test_valid_media_paths(path):
    assert validate_media_reference(path)


@pytest.mark.parametrize("path", ["javascript:alert(1)", "data:image/svg+xml,test", "file:///a.png",
                                  "//example.com/a.png", "https://user:pass@example.com/a.png",
                                  "tb/../private.png", "tb/%2e%2e/private.png", "tb/a.xlsx",
                                  "tb/evil\\a.png", "java\nscript:alert(1)", "https://[broken"])
def test_unsafe_media_paths(path):
    assert not validate_media_reference(path)


def test_uploaded_media_must_exist(tmp_path):
    assert not validate_media_reference('/api/v1/media/' + 'a' * 32 + '.png', tmp_path)
    assert not validate_media_reference('/api/v1/media/../a.png', tmp_path)


def test_legacy_catalog_models_reject_unsafe_images():
    from pydantic import ValidationError
    from backend.admin_routes import ProductColorRequest, ConfigOptionUpdateRequest
    for model, fields in ((ProductColorRequest, {"code": "red", "label": "Red"}),
                          (ConfigOptionUpdateRequest, {})):
        with pytest.raises(ValidationError):
            model(image_path="javascript:alert(1)", **fields)
        assert model(image_path="tb/product.png", **fields).image_path == "tb/product.png"
