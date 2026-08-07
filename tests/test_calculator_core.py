from tools.calculator.core import evaluate_expression


def test_evaluates_arithmetic_with_parentheses_and_power():
    result = evaluate_expression("(2 + 3) ** 2")

    assert result.success is True
    assert result.result == "25"


def test_evaluates_exact_large_integer():
    result = evaluate_expression("123456789 * 987654321")

    assert result.success is True
    assert result.result == "121932631112635269"


def test_rejects_function_calls_not_in_allowlist():
    result = evaluate_expression("__import__('os').system('whoami')")

    assert result.success is False
    assert result.error.code == "unsupported_syntax"


def test_returns_structured_division_by_zero_error():
    result = evaluate_expression("1 / 0")

    assert result.success is False
    assert result.error.code == "division_by_zero"


def test_supports_percentage_literal_and_modulo():
    assert evaluate_expression("50%").result == "0.5"
    assert evaluate_expression("17 % 5").result == "2"


def test_supports_common_scientific_functions():
    assert evaluate_expression("sqrt(16)").result == "4"
    assert evaluate_expression("log(100, 10)").result == "2"
    assert evaluate_expression("ln(e)").result == "1"


def test_supports_degree_trigonometry():
    result = evaluate_expression("sin(90)", angle_unit="deg")

    assert result.success is True
    assert abs(float(result.result) - 1.0) < 1e-10


def test_rejects_unknown_names_and_malformed_input():
    unknown = evaluate_expression("answer + 1")
    malformed = evaluate_expression("2 +")

    assert unknown.success is False
    assert unknown.error.code == "unknown_name"
    assert malformed.success is False
    assert malformed.error.code == "invalid_expression"


def test_rejects_oversized_expression():
    result = evaluate_expression("1" * 501)

    assert result.success is False
    assert result.error.code == "expression_too_long"
