from app.services.tool_router import CalculatorRouter


def test_router_extracts_chinese_arithmetic_expression():
    invocation = CalculatorRouter.route("请计算 123456789 × 987654321 等于多少？")

    assert invocation is not None
    assert invocation.request == {"mode": "arithmetic", "expression": "123456789*987654321"}


def test_router_extracts_unit_conversion():
    invocation = CalculatorRouter.route("把 5 公里换算成米")

    assert invocation is not None
    assert invocation.request == {
        "mode": "unit",
        "value": 5,
        "from_unit": "公里",
        "to_unit": "米",
    }


def test_router_extracts_equation():
    invocation = CalculatorRouter.route("解方程 x**2 - 5*x + 6 = 0")

    assert invocation is not None
    assert invocation.request["mode"] == "equation"
    assert invocation.request["equation"] == "x**2 - 5*x + 6 = 0"
    assert invocation.request["variables"] == ["x"]


def test_router_ignores_normal_question():
    assert CalculatorRouter.route("Embedding 是什么？") is None


def test_router_extracts_scientific_function_without_parentheses():
    invocation = CalculatorRouter.route("sin372637是多少？")

    assert invocation is not None
    assert invocation.request == {
        "mode": "arithmetic",
        "expression": "sin(372637)",
    }


def test_router_detects_explicit_degree_angle():
    invocation = CalculatorRouter.route("sin 90 度是多少？")

    assert invocation is not None
    assert invocation.request == {
        "mode": "arithmetic",
        "expression": "sin(90)",
        "angle_unit": "deg",
    }
