from tools.calculator.tool import calculator_tool


def test_calculator_tool_exposes_agent_metadata():
    schema = calculator_tool.schema()

    assert calculator_tool.name == "calculator"
    assert "科学" in calculator_tool.description
    assert schema["name"] == "calculator"
    assert "properties" in schema["parameters"]


def test_dispatches_explicit_arithmetic_and_unit_modes():
    arithmetic = calculator_tool.run({"mode": "arithmetic", "expression": "2 + 3 * 4"})
    unit = calculator_tool.run({"mode": "unit", "value": 5, "from_unit": "km", "to_unit": "m"})

    assert arithmetic["success"] is True
    assert arithmetic["result"] == "14"
    assert unit["success"] is True
    assert unit["result"] == "5000"


def test_dispatches_matrix_equation_and_symbolic_modes():
    matrix = calculator_tool.run(
        {"mode": "matrix", "operation": "multiply", "left": [[1, 2]], "right": [[3], [4]]}
    )
    equation = calculator_tool.run(
        {"mode": "equation", "equation": "x**2 - 5*x + 6 = 0", "variables": ["x"]}
    )
    derivative = calculator_tool.run(
        {"mode": "symbolic", "operation": "differentiate", "expression": "x**2", "variable": "x"}
    )

    assert matrix["result"] == [[11]]
    assert equation["result"] == ["2", "3"]
    assert derivative["result"] == "2*x"


def test_auto_mode_recognizes_arithmetic_and_equation():
    arithmetic = calculator_tool.run({"expression": "2 ** 8"})
    equation = calculator_tool.run(
        {"expression": "x + 2 = 5", "variables": ["x"]}
    )

    assert arithmetic["mode"] == "arithmetic"
    assert arithmetic["result"] == "256"
    assert equation["mode"] == "equation"
    assert equation["result"] == ["3"]


def test_unknown_mode_returns_structured_error():
    result = calculator_tool.run({"mode": "weather", "expression": "1 + 1"})

    assert result["success"] is False
    assert result["error"]["code"] == "unsupported_mode"
