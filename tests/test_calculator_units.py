from tools.calculator.units import convert_unit


def test_converts_length_with_aliases():
    result = convert_unit(5, "公里", "m")

    assert result.success is True
    assert result.result == "5000"


def test_converts_temperature():
    result = convert_unit(100, "degC", "degF")

    assert result.success is True
    assert result.result == "212"


def test_converts_speed():
    result = convert_unit(36, "km/h", "m/s")

    assert result.success is True
    assert result.result == "10"


def test_rejects_incompatible_units():
    result = convert_unit(1, "m", "kg")

    assert result.success is False
    assert result.error.code == "incompatible_units"


def test_rejects_unknown_units():
    result = convert_unit(1, "made_up_unit", "m")

    assert result.success is False
    assert result.error.code == "unknown_unit"
