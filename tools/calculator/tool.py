from __future__ import annotations

from typing import Any

from .core import evaluate_expression
from .equations import solve_equation
from .matrix import (
    matrix_add,
    matrix_determinant,
    matrix_inverse,
    matrix_multiply,
    matrix_subtract,
    matrix_transpose,
    solve_linear_system,
)
from .schemas import CalculatorError, CalculatorRequest, CalculatorResult
from .symbolic import differentiate_expression, integrate_expression, simplify_expression
from .units import convert_unit


class CalculatorTool:
    name = "calculator"
    description = "执行科学计算、单位换算、矩阵运算、方程求解和符号计算的本地工具。"

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["auto", "arithmetic", "unit", "matrix", "equation", "symbolic"],
                    },
                    "expression": {"type": "string"},
                    "angle_unit": {"type": "string", "enum": ["rad", "deg"]},
                    "value": {"type": "number"},
                    "from_unit": {"type": "string"},
                    "to_unit": {"type": "string"},
                    "operation": {"type": "string"},
                    "left": {"type": "array"},
                    "right": {"type": "array"},
                    "matrix": {"type": "array"},
                    "vector": {"type": "array"},
                    "equation": {"type": "string"},
                    "variables": {"type": "array", "items": {"type": "string"}},
                    "variable": {"type": "string"},
                    "lower": {"type": "string"},
                    "upper": {"type": "string"},
                },
                "additionalProperties": False,
            },
        }

    def run(self, request: dict[str, Any] | CalculatorRequest) -> dict[str, Any]:
        try:
            parsed = request if isinstance(request, CalculatorRequest) else CalculatorRequest.from_dict(request)
        except (TypeError, ValueError, AttributeError):
            return self._failure("auto", None, "invalid_request", "计算请求必须是对象")

        mode = parsed.mode.lower().strip()
        if mode == "auto":
            mode = self._infer_mode(parsed)
        result = self._dispatch(mode, parsed)
        return result.to_dict()

    def _infer_mode(self, request: CalculatorRequest) -> str:
        if request.equation:
            return "equation"
        if request.from_unit or request.to_unit or request.value is not None:
            return "unit"
        if request.operation in {"add", "subtract", "multiply", "transpose", "determinant", "inverse", "solve"}:
            return "matrix"
        if request.operation in {"simplify", "differentiate", "integrate"}:
            return "symbolic"
        if request.expression and "=" in request.expression and request.variables:
            return "equation"
        return "arithmetic"

    def _dispatch(self, mode: str, request: CalculatorRequest) -> CalculatorResult:
        if mode == "arithmetic":
            if request.expression is None:
                return self._failure(mode, None, "missing_expression", "算术计算需要 expression")
            return evaluate_expression(request.expression, angle_unit=request.angle_unit)
        if mode == "unit":
            if request.value is None or not request.from_unit or not request.to_unit:
                return self._failure(mode, request.expression, "missing_unit_fields", "单位换算需要 value、from_unit 和 to_unit")
            return convert_unit(request.value, request.from_unit, request.to_unit)
        if mode == "matrix":
            return self._dispatch_matrix(request)
        if mode == "equation":
            equation = request.equation or request.expression
            if not equation or not request.variables:
                return self._failure(mode, equation, "missing_equation_fields", "方程求解需要 equation 和 variables")
            return solve_equation(equation, request.variables)
        if mode == "symbolic":
            return self._dispatch_symbolic(request)
        return self._failure(mode, request.expression, "unsupported_mode", f"不支持的计算模式：{mode}")

    def _dispatch_matrix(self, request: CalculatorRequest) -> CalculatorResult:
        operation = request.operation or "multiply"
        left = request.left or request.matrix
        right = request.right
        if operation == "add" and left is not None and right is not None:
            return matrix_add(left, right)
        if operation == "subtract" and left is not None and right is not None:
            return matrix_subtract(left, right)
        if operation == "multiply" and left is not None and right is not None:
            return matrix_multiply(left, right)
        if operation == "transpose" and left is not None:
            return matrix_transpose(left)
        if operation == "determinant" and left is not None:
            return matrix_determinant(left)
        if operation == "inverse" and left is not None:
            return matrix_inverse(left)
        if operation == "solve" and left is not None and request.vector is not None:
            return solve_linear_system(left, request.vector)
        return self._failure("matrix", None, "missing_matrix_fields", "矩阵运算参数不完整")

    def _dispatch_symbolic(self, request: CalculatorRequest) -> CalculatorResult:
        if not request.expression:
            return self._failure("symbolic", None, "missing_expression", "符号计算需要 expression")
        if request.operation == "simplify" or request.operation is None:
            return simplify_expression(request.expression)
        if request.operation == "differentiate" and request.variable:
            return differentiate_expression(request.expression, request.variable)
        if request.operation == "integrate" and request.variable:
            return integrate_expression(request.expression, request.variable, request.lower, request.upper)
        return self._failure("symbolic", request.expression, "missing_symbolic_fields", "符号计算参数不完整")

    @staticmethod
    def _failure(mode: str, expression: str | None, code: str, message: str) -> CalculatorResult:
        return CalculatorResult(False, mode, expression, error=CalculatorError(code, message))


calculator_tool = CalculatorTool()
