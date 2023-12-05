"""
Implements tests for alfredo_lib.controllers.validator module
"""
import pytest

from alfredo_lib.controllers import validator


@pytest.mark.parametrize(
    ('user_input', 'allow_negative', 'want', 'want_err'),
    (
       (1, False, 1, None),
    )
)
def test_number_to_percent(user_input, allow_negative, want, want_err):
    "Tests number_to_percent of validator module"
    test_validator = validator.InputController(input_schemas={})

    perc, err = test_validator.number_to_percent(
        user_input=user_input, 
        allow_negative=allow_negative
    )
    if want_err is None:
        assert err is None
        assert perc == want
    else:
        assert isinstance(want_err, ValueError) is True
        assert perc is want
