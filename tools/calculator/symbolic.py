from __future__ import annotations

import re
from typing import Any

import sympy as sp
from sympy.parsing.sympy_parser import parse_expr, standard_transformations

from .schemas import CalculatorError, CalculatorResult

MAX_SYMBOLIC_LENGTH = 500
MAX_SYMBOLIC_OPERATIONS = 200
_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_]\w*")
_ALLOWED_FUNCTIONS = {
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "sqrt": sp.sqrt,
    "log": sp.log,
    "ln": sp.log,
    "exp": sp.exp,
    "abs": sp.Abs,
}
_ALLOWED_CONSTANTS = {"pi": sp.pi, "E": sp.E}
_DEFAULT_SYMBOL_NAMES = {"x", "y", "z", "t", "a", "b", "c", "n"}


def _failure(expression: str, code: str, message: str, mode: str = "symbolic") -> CalculatorResult:
    return CalculatorResult(
        success=False,
        mode=mode,
        expression=expression,
        error=CalculatorError(code, message),
    )


def _validate_variable(variable: str) -> CalculatorResult | None:
    if not isinstance(variable, str) or not variable.isidentifier() or variable.startswith("__"):
        return _failure(str(variable), "invalid_variable", "变量名必须是普通标识符")
    return None


def _parse(expression: str, variables: list[str] | None = None) -> tuple[sp.Expr | None, CalculatorResult | None]:
    expression = str(expression).strip()
    if not expression:
        return None, _failure(expression, "empty_expression", "符号表达式不能为空")
    if len(expression) > MAX_SYMBOLIC_LENGTH:
        return None, _failure(expression, "expression_too_long", "符号表达式长度不能超过 500 个字符")
    if "__" in expression or not re.fullmatch(r"[A-Za-z0-9_+\-*/%^().,\s]+", expression):
        return None, _failure(expression, "unsupported_syntax", "符号表达式包含不支持的字符")

    variable_names = set(variables or [])
    local_dict: dict[str, Any] = {name: sp.Symbol(name) for name in variable_names}
    local_dict.update(_ALLOWED_FUNCTIONS)
    local_dict.update(_ALLOWED_CONSTANTS)
    for name in _IDENTIFIER_PATTERN.findall(expression):
        if name in local_dict:
            continue
        if variables is None and name in _DEFAULT_SYMBOL_NAMES:
            local_dict[name] = sp.Symbol(name)
            continue
        return None, _failure(expression, "unknown_name", f"未知名称：{name}")

    try:
        parsed = parse_expr(
            expression.replace("^", "**"),
            local_dict=local_dict,
            transformations=standard_transformations,
            evaluate=True,
        )
    except (SyntaxError, TypeError, ValueError, NameError):
        return None, _failure(expression, "invalid_expression", "符号表达式格式无效")
    if sp.count_ops(parsed) > MAX_SYMBOLIC_OPERATIONS:
        return None, _failure(expression, "expression_too_complex", "符号表达式过于复杂")
    return parsed, None


def _success(expression: str, result: Any, steps: list[str] | None = None) -> CalculatorResult:
    return CalculatorResult(True, "symbolic", expression, str(result), steps or [])


def simplify_expression(expression: str) -> CalculatorResult:
    parsed, error = _parse(expression)
    if error:
        return error
    try:
        return _success(expression, sp.simplify(parsed))
    except Exception:
        return _failure(expression, "symbolic_error", "符号化简失败")


def differentiate_expression(expression: str, variable: str) -> CalculatorResult:
    variable_error = _validate_variable(variable)
    if variable_error:
        return variable_error
    parsed, error = _parse(expression, [variable])
    if error:
        return error
    try:
        return _success(expression, sp.diff(parsed, sp.Symbol(variable)))
    except Exception:
        return _failure(expression, "symbolic_error", "求导失败")


def integrate_expression(
    expression: str,
    variable: str,
    lower: str | None = None,
    upper: str | None = None,
) -> CalculatorResult:
    variable_error = _validate_variable(variable)
    if variable_error:
        return variable_error
    parsed, error = _parse(expression, [variable])
    if error:
        return error
    symbol = sp.Symbol(variable)
    try:
        if lower is None or upper is None:
            result = sp.integrate(parsed, symbol)
        else:
            lower_expr, lower_error = _parse(str(lower), [variable])
            upper_expr, upper_error = _parse(str(upper), [variable])
            if lower_error:
                return lower_error
            if upper_error:
                return upper_error
            result = sp.integrate(parsed, (symbol, lower_expr, upper_expr))
        return _success(expression, result)
    except Exception:
        return _failure(expression, "symbolic_error", "积分失败")
