import pytest
from pydantic import ValidationError

from backend.admin_routes import CreateStaffRequest, UserUpdateRequest, UserPasswordResetRequest


@pytest.mark.parametrize("model,extra", [
    (CreateStaffRequest, {}),
    (UserUpdateRequest, {"version": 1}),
    (UserPasswordResetRequest, {"version": 1}),
])
def test_admin_passwords_are_bounded_before_processing(model, extra):
    assert model(password="a" * 1024, **extra).password == "a" * 1024
    with pytest.raises(ValidationError):
        model(password="a" * 1025, **extra)


def test_optional_password_can_be_omitted():
    assert UserUpdateRequest(version=1).password is None
