from tools.calculator.matrix import (
    matrix_add,
    matrix_determinant,
    matrix_inverse,
    matrix_multiply,
    matrix_subtract,
    matrix_transpose,
    solve_linear_system,
)


def test_matrix_multiply_and_addition():
    left = [[1, 2], [3, 4]]
    right = [[5, 6], [7, 8]]

    assert matrix_multiply(left, right).result == [[19, 22], [43, 50]]
    assert matrix_add(left, right).result == [[6, 8], [10, 12]]
    assert matrix_subtract(right, left).result == [[4, 4], [4, 4]]


def test_matrix_transpose_and_determinant():
    matrix = [[1, 2, 3], [4, 5, 6]]

    assert matrix_transpose(matrix).result == [[1, 4], [2, 5], [3, 6]]
    assert matrix_determinant([[1, 2], [3, 4]]).result == "-2"


def test_matrix_inverse_and_linear_system():
    inverse = matrix_inverse([[4, 7], [2, 6]])
    solution = solve_linear_system([[2, 1], [1, -1]], [5, 1])

    assert inverse.success is True
    assert abs(inverse.result[0][0] - 0.6) < 1e-10
    assert solution.result == [2, 1]


def test_rejects_dimension_mismatch():
    result = matrix_multiply([[1, 2]], [[1, 2]])

    assert result.success is False
    assert result.error.code == "dimension_mismatch"


def test_rejects_singular_matrix_inverse():
    result = matrix_inverse([[1, 2], [2, 4]])

    assert result.success is False
    assert result.error.code == "singular_matrix"
