"""
Implements tests for alfredo_lib.controllers.validator module
"""
import pytest

from alfredo_lib.controllers import validator


@pytest.mark.parametrize(
    ('user_input', 'allow_negative', 'want', 'want_err', 'test_name'),
    (
       (1, False, 1, None, 'Happy path, no negatives'),
    )
)
def test_number_to_percent(user_input, allow_negative, want, want_err, test_name):
    "Tests number_to_percent of validator module"
    test_validator = validator.InputController(input_schemas={})

    perc, err = test_validator.number_to_percent(
        user_input=user_input, 
        allow_negative=allow_negative
    )
    # Google how to test funcs that return a tuple
        # Chat gpt gives BS
    if want_err is not None:
         # hard coding value error is not good
        assert isinstance(want_err, ValueError) is True
        assert perc is want
        return
    assert err is None
    assert perc == want
    assert 1 == 0
    

   
