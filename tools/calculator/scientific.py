from __future__ import annotations

import math
from typing import Callable


def _trig(function: Callable[[float], float], angle_unit: str) -> Callable[[float], float]:
    def wrapped(value: float) -> float:
        radians = math.radians(value) if angle_unit == "deg" else value
        return function(radians)

    return wrapped


def _inverse_trig(function: Callable[[float], float], angle_unit: str) -> Callable[[float], float]:
    def wrapped(value: float) -> float:
        result = function(value)
        return math.degrees(result) if angle_unit == "deg" else result

    return wrapped


def scientific_namespace(angle_unit: str = "rad") -> tuple[dict[str, Callable], dict[str, float]]:
    if angle_unit not in {"rad", "deg"}:
        raise ValueError("角度单位只能是 rad 或 deg")
    functions: dict[str, Callable] = {
        "sqrt": math.sqrt,
        "abs": abs,
        "round": round,
        "sin": _trig(math.sin, angle_unit),
        "cos": _trig(math.cos, angle_unit),
        "tan": _trig(math.tan, angle_unit),
        "asin": _inverse_trig(math.asin, angle_unit),
        "acos": _inverse_trig(math.acos, angle_unit),
        "atan": _inverse_trig(math.atan, angle_unit),
        "log": math.log,
        "ln": math.log,
        "exp": math.exp,
    }
    return functions, {"pi": math.pi, "e": math.e}
