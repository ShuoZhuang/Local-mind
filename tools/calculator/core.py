from __future__ import annotations

import ast
import math
import operator
import re
from typing import Any, Callable

from .schemas import CalculatorError, CalculatorResult

MAX_EXPRESSION_LENGTH = 500
MAX_AST_DEPTH = 30
MAX_EXPONENT = 1000

_PERCENTAGE_PATTERN = re.compile(
    r"(?<![\w.])([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)%"
)

_BINARY_OPERATORS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _error(expression: str, code: str, message: str) -> CalculatorResult:
    return CalculatorResult(
        success=False,
        mode="arithmetic",
        expression=expression,
        error=CalculatorError(code, message),
    )


def _format_number(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("结果不是数字")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("结果不是有限数字")
        if value == 0:
            return "0"
        if value.is_integer() and abs(value) < 10**18:
            return str(int(value))
        return format(value, ".15g")
    return str(value)


def _normalize_percentages(expression: str) -> str:
    return _PERCENTAGE_PATTERN.sub(r"(\1 / 100)", expression)


def _ast_depth(node: ast.AST, depth: int = 0) -> int:
    if depth > MAX_AST_DEPTH:
        return depth
    children = list(ast.iter_child_nodes(node))
    if not children:
        return depth
    return max(_ast_depth(child, depth + 1) for child in children)


def _evaluate_node(
    node: ast.AST,
    functions: dict[str, Callable[..., Any]],
    constants: dict[str, Any],
) -> Any:
    if isinstance(node, ast.Expression):
        return _evaluate_node(node.body, functions, constants)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in constants:
            return constants[node.id]
        raise KeyError(node.id)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_evaluate_node(node.operand, functions, constants))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _evaluate_node(node.left, functions, constants)
        right = _evaluate_node(node.right, functions, constants)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise OverflowError("指数过大")
        return _BINARY_OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        function = functions.get(node.func.id)
        if function is None:
            raise LookupError(node.func.id)
        if node.keywords:
            raise SyntaxError("不支持关键字参数")
        return function(*[_evaluate_node(arg, functions, constants) for arg in node.args])
    raise SyntaxError("包含不支持的语法")


def evaluate_expression(
    expression: str,
    *,
    angle_unit: str = "rad",
    functions: dict[str, Callable[..., Any]] | None = None,
    constants: dict[str, Any] | None = None,
) -> CalculatorResult:
    expression = str(expression).strip()
    if not expression:
        return _error(expression, "empty_expression", "表达式不能为空")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        return _error(expression, "expression_too_long", "表达式长度不能超过 500 个字符")
    if angle_unit not in {"rad", "deg"}:
        return _error(expression, "invalid_angle_unit", "角度单位只能是 rad 或 deg")

    normalized = _normalize_percentages(expression)
    try:
        tree = ast.parse(normalized, mode="eval")
    except (SyntaxError, ValueError, MemoryError):
        return _error(expression, "invalid_expression", "表达式格式无效")
    if _ast_depth(tree) > MAX_AST_DEPTH:
        return _error(expression, "expression_too_deep", "表达式嵌套层级过深")

    if functions is None and constants is None:
        from .scientific import scientific_namespace

        function_map, constant_map = scientific_namespace(angle_unit)
    else:
        function_map = functions or {}
        constant_map = constants or {}
    try:
        value = _evaluate_node(tree, function_map, constant_map)
        result = _format_number(value)
    except KeyError as exc:
        return _error(expression, "unknown_name", f"未知名称：{exc.args[0]}")
    except LookupError as exc:
        return _error(expression, "unknown_function", f"未知函数：{exc.args[0]}")
    except ZeroDivisionError:
        return _error(expression, "division_by_zero", "除数不能为 0")
    except OverflowError:
        return _error(expression, "numeric_overflow", "计算结果超出允许范围")
    except (TypeError, ValueError):
        return _error(expression, "math_domain_error", "数学函数或运算的输入不在有效范围内")
    except SyntaxError:
        return _error(expression, "unsupported_syntax", "表达式包含不支持的语法")
    except Exception:
        return _error(expression, "calculation_error", "计算失败")

    return CalculatorResult(success=True, mode="arithmetic", expression=expression, result=result)
