"""
Implements tests for alfredo_lib.controllers.validator module
"""
import pytest

from alfredo_lib.controllers import validator


@pytest.mark.parametrize(
    ("name", "input_schemas", "want"),
    (
        (
            "Happy path, only base schema present",
            {
                "user": {"base": {"username": "str", "spreadsheet": "str"}}
            },
            {
                "user": {"username": "str", "spreadsheet": "str"}
            }
        ),
        (
            "Happy path: base+extra and multiple models",
            {
                "user": {
                    "base": {"username": "str", "spreadsheet": "str"},
                    "extra": {"timezone": "str"}
                },
                "transaction": {
                    "base": {"amount": "float"}, "extra": {"comment": "str"}
                }
            },
            {
                "user": {"username": "str", "spreadsheet": "str", "timezone": "str"},
                "transaction": {"amount": "float", "comment": "str"}
            }
        ),
        ("Empty schema",{},{})
    )
)
def test_parse_types_schema(name, input_schemas, want):
    "Tests _parse_types_schema of validator module"
    got = validator.InputController._parse_types_schema(
        input_schemas=input_schemas
    )
    assert got == want


@pytest.mark.parametrize(
    ("name", "user_input", "allow_negative", "want", "err"),
    (
       ("Happy path, percentage input, no negatives", 1, False, 1, None),
       ("Happy path, conversion needed, no negatives", 50, False, 0.5, None, ),
       ("Conversion failed: input too high, no negatives", 500, False, None, ValueError("smth")),
       ("Unexpected negative value", -20, False, None, ValueError("smth")),
       ("Expected negative value", -20, True, -0.2, None)
    )
)
def test_number_to_percent(name, user_input, allow_negative, want, err):
    "Tests number_to_percent of validator module"
    got, e = validator.InputController.number_to_percent(
        user_input=user_input, 
        allow_negative=allow_negative
    )
    # Google how to test funcs that return a tuple
        # Chat gpt gives BS
    if e is not None:
        assert type(e) == type(err)
        assert got is want
        return
    assert err is None
    assert got == want

@pytest.mark.parametrize(
    ("name", "data", "target_type", "want", "err"),
    (
        ("Happy path for string", " bla ", "str", "bla", None),
        ("Happy path for float", " 0.75 ", "float", 0.75, None),
        ("Happy path for int", " 10 ", "int", 10, None),
        ("Unsupported target type", " 10 ", "float64", None, NotImplementedError("smth"))
    )
)
def test_convert_type(name, data, target_type, want, err):
    "Tests number_to_percent of validator module"
    got, e = validator.InputController._convert_type(
        data=data, target_type=target_type
    )
    if e is not None:
        assert type(e) == type(err)
        assert got is want
        return
    assert err is None
    assert got == want
    

   
