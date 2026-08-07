from tools.calculator.equations import solve_equation
from tools.calculator.symbolic import (
    differentiate_expression,
    integrate_expression,
    simplify_expression,
)


def test_solves_quadratic_equation():
    result = solve_equation("x**2 - 5*x + 6 = 0", ["x"])

    assert result.success is True
    assert result.result == ["2", "3"]


def test_simplifies_expression():
    result = simplify_expression("(x + 1)**2 - x**2 - 2*x")

    assert result.success is True
    assert result.result == "1"


def test_differentiates_expression():
    result = differentiate_expression("x**3 + x", "x")

    assert result.success is True
    assert result.result == "3*x**2 + 1"


def test_integrates_expression_with_bounds():
    result = integrate_expression("x", "x", "0", "2")

    assert result.success is True
    assert result.result == "2"


def test_rejects_non_identifier_variable_name():
    result = differentiate_expression("x + 1", "__import__('os')")

    assert result.success is False
    assert result.error.code == "invalid_variable"


def test_rejects_unknown_symbolic_name():
    result = simplify_expression("x + malicious_name")

    assert result.success is False
    assert result.error.code == "unknown_name"
