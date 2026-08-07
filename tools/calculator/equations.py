from __future__ import annotations

import sympy as sp

from .schemas import CalculatorError, CalculatorResult
from .symbolic import _failure, _parse


def solve_equation(equation: str, variables: list[str]) -> CalculatorResult:
    expression = str(equation).strip()
    if not variables or any(not name.isidentifier() or name.startswith("__") for name in variables):
        return _failure(expression, "invalid_variable", "变量名必须是普通标识符", mode="equation")
    if expression.count("=") > 1:
        return _failure(expression, "invalid_equation", "方程只能包含一个等号", mode="equation")
    if "=" in expression:
        left_text, right_text = expression.split("=", 1)
    else:
        left_text, right_text = expression, "0"
    left, left_error = _parse(left_text, variables)
    right, right_error = _parse(right_text, variables)
    if left_error:
        left_error.mode = "equation"
        return left_error
    if right_error:
        right_error.mode = "equation"
        return right_error
    try:
        symbols = [sp.Symbol(name) for name in variables]
        solutions = sp.solve(sp.Eq(left, right), symbols, dict=False)
        if len(variables) == 1:
            solutions = sorted(solutions, key=sp.default_sort_key)
        formatted = [str(solution) for solution in solutions]
        return CalculatorResult(True, "equation", expression, formatted)
    except (NotImplementedError, ValueError):
        return _failure(expression, "equation_error", "方程暂时无法求解", mode="equation")
    except Exception:
        return _failure(expression, "symbolic_error", "方程求解失败", mode="equation")
