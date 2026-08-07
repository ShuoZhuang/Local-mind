from __future__ import annotations

from typing import Any

from .schemas import CalculatorError, CalculatorResult

try:
    import pint
except ImportError:  # pragma: no cover - dependency setup reports this clearly
    pint = None


_UNIT_ALIASES = {
    "米": "meter",
    "公尺": "meter",
    "m": "meter",
    "千米": "kilometer",
    "公里": "kilometer",
    "km": "kilometer",
    "厘米": "centimeter",
    "公分": "centimeter",
    "cm": "centimeter",
    "毫米": "millimeter",
    "mm": "millimeter",
    "英寸": "inch",
    "in": "inch",
    "英尺": "foot",
    "ft": "foot",
    "平方米": "meter ** 2",
    "平方公里": "kilometer ** 2",
    "平方厘米": "centimeter ** 2",
    "升": "liter",
    "l": "liter",
    "L": "liter",
    "毫升": "milliliter",
    "ml": "milliliter",
    "立方米": "meter ** 3",
    "千克": "kilogram",
    "公斤": "kilogram",
    "kg": "kilogram",
    "克": "gram",
    "g": "gram",
    "毫克": "milligram",
    "mg": "milligram",
    "秒": "second",
    "s": "second",
    "分钟": "minute",
    "min": "minute",
    "小时": "hour",
    "h": "hour",
    "天": "day",
    "d": "day",
    "米每秒": "meter / second",
    "m/s": "meter / second",
    "公里每小时": "kilometer / hour",
    "km/h": "kilometer / hour",
    "摄氏度": "degC",
    "℃": "degC",
    "degC": "degC",
    "华氏度": "degF",
    "℉": "degF",
    "degF": "degF",
    "开尔文": "kelvin",
    "K": "kelvin",
    "字节": "byte",
    "B": "byte",
    "KB": "kilobyte",
    "MB": "megabyte",
    "GB": "gigabyte",
    "GiB": "gibibyte",
}


def _format_value(value: Any) -> str:
    magnitude = float(value)
    if magnitude.is_integer() and abs(magnitude) < 10**18:
        return str(int(magnitude))
    return format(magnitude, ".15g")


def _failure(expression: str, code: str, message: str) -> CalculatorResult:
    return CalculatorResult(
        success=False,
        mode="unit",
        expression=expression,
        error=CalculatorError(code, message),
    )


def convert_unit(value: float | int, from_unit: str, to_unit: str) -> CalculatorResult:
    expression = f"{value} {from_unit} -> {to_unit}"
    if pint is None:
        return _failure(expression, "missing_dependency", "单位换算需要安装 pint")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return _failure(expression, "invalid_value", "换算值必须是数字")
    source = _UNIT_ALIASES.get(str(from_unit).strip(), str(from_unit).strip())
    target = _UNIT_ALIASES.get(str(to_unit).strip(), str(to_unit).strip())
    try:
        registry = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)
        converted = registry.Quantity(value, source).to(target)
        return CalculatorResult(
            success=True,
            mode="unit",
            expression=expression,
            result=_format_value(converted.magnitude),
            steps=[f"{value} {from_unit} = {_format_value(converted.magnitude)} {to_unit}"],
        )
    except pint.errors.DimensionalityError:
        return _failure(expression, "incompatible_units", "两个单位不兼容")
    except pint.errors.UndefinedUnitError:
        return _failure(expression, "unknown_unit", "无法识别其中一个单位")
    except (TypeError, ValueError):
        return _failure(expression, "invalid_unit_expression", "单位表达式无效")
