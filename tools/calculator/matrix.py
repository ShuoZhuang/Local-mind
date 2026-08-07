from __future__ import annotations

from typing import Any, Callable

import numpy as np

from .schemas import CalculatorError, CalculatorResult

MAX_MATRIX_DIMENSION = 32


def _failure(operation: str, code: str, message: str) -> CalculatorResult:
    return CalculatorResult(
        success=False,
        mode="matrix",
        expression=operation,
        error=CalculatorError(code, message),
    )


def _matrix(value: Any) -> np.ndarray | None:
    array = np.asarray(value, dtype=float)
    if array.ndim != 2 or any(size == 0 or size > MAX_MATRIX_DIMENSION for size in array.shape):
        return None
    if not np.isfinite(array).all():
        return None
    return array


def _vector(value: Any) -> np.ndarray | None:
    array = np.asarray(value, dtype=float)
    if array.ndim != 1 or array.size == 0 or array.size > MAX_MATRIX_DIMENSION:
        return None
    if not np.isfinite(array).all():
        return None
    return array


def _clean(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [_clean(item) for item in value.tolist()]
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if abs(number) < 1e-12:
            return 0
        if number.is_integer() and abs(number) < 10**15:
            return int(number)
        return number
    if isinstance(value, (int, np.integer)):
        return int(value)
    return value


def _binary_operation(
    operation: str,
    left: Any,
    right: Any,
    function: Callable[[np.ndarray, np.ndarray], np.ndarray],
) -> CalculatorResult:
    left_array = _matrix(left)
    right_array = _matrix(right)
    if left_array is None or right_array is None:
        return _failure(operation, "invalid_matrix", "矩阵必须是有限数字组成的二维数组，且每边不超过 32")
    try:
        result = function(left_array, right_array)
    except ValueError:
        return _failure(operation, "dimension_mismatch", "矩阵维度不匹配")
    return CalculatorResult(True, "matrix", operation, _clean(result))


def matrix_add(left: list[list[float]], right: list[list[float]]) -> CalculatorResult:
    return _binary_operation("add", left, right, np.add)


def matrix_subtract(left: list[list[float]], right: list[list[float]]) -> CalculatorResult:
    return _binary_operation("subtract", left, right, np.subtract)


def matrix_multiply(left: list[list[float]], right: list[list[float]]) -> CalculatorResult:
    return _binary_operation("multiply", left, right, np.matmul)


def matrix_transpose(matrix: list[list[float]]) -> CalculatorResult:
    array = _matrix(matrix)
    if array is None:
        return _failure("transpose", "invalid_matrix", "矩阵必须是有限数字组成的二维数组，且每边不超过 32")
    return CalculatorResult(True, "matrix", "transpose", _clean(array.T))


def matrix_determinant(matrix: list[list[float]]) -> CalculatorResult:
    array = _matrix(matrix)
    if array is None:
        return _failure("determinant", "invalid_matrix", "矩阵必须是有限数字组成的二维数组，且每边不超过 32")
    if array.shape[0] != array.shape[1]:
        return _failure("determinant", "dimension_mismatch", "行列式需要方阵")
    try:
        determinant = float(np.linalg.det(array))
    except np.linalg.LinAlgError:
        return _failure("determinant", "singular_matrix", "无法计算该矩阵的行列式")
    return CalculatorResult(True, "matrix", "determinant", _format_scalar(determinant))


def matrix_inverse(matrix: list[list[float]]) -> CalculatorResult:
    array = _matrix(matrix)
    if array is None:
        return _failure("inverse", "invalid_matrix", "矩阵必须是有限数字组成的二维数组，且每边不超过 32")
    if array.shape[0] != array.shape[1]:
        return _failure("inverse", "dimension_mismatch", "逆矩阵需要方阵")
    try:
        result = np.linalg.inv(array)
    except np.linalg.LinAlgError:
        return _failure("inverse", "singular_matrix", "该矩阵不可逆")
    return CalculatorResult(True, "matrix", "inverse", _clean(result))


def solve_linear_system(matrix: list[list[float]], vector: list[float]) -> CalculatorResult:
    array = _matrix(matrix)
    values = _vector(vector)
    if array is None or values is None:
        return _failure("solve", "invalid_matrix", "矩阵和向量必须是有限数字数组")
    if array.shape[0] != array.shape[1] or array.shape[0] != values.size:
        return _failure("solve", "dimension_mismatch", "线性方程组的矩阵和向量维度不匹配")
    try:
        result = np.linalg.solve(array, values)
    except np.linalg.LinAlgError:
        return _failure("solve", "singular_matrix", "线性方程组没有唯一解")
    return CalculatorResult(True, "matrix", "solve", _clean(result))


def _format_scalar(value: float) -> str:
    if abs(value) < 1e-12:
        value = 0.0
    if value.is_integer() and abs(value) < 10**15:
        return str(int(value))
    return format(value, ".15g")
