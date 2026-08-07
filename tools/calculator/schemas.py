from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CalculatorError:
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass
class CalculatorResult:
    success: bool
    mode: str
    expression: str | None = None
    result: Any = None
    steps: list[str] = field(default_factory=list)
    error: CalculatorError | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "mode": self.mode,
            "expression": self.expression,
            "result": self.result,
            "steps": list(self.steps),
            "error": self.error.to_dict() if self.error else None,
        }


@dataclass
class CalculatorRequest:
    mode: str = "auto"
    expression: str | None = None
    angle_unit: str = "rad"
    value: float | int | None = None
    from_unit: str | None = None
    to_unit: str | None = None
    matrix: list[list[float]] | None = None
    left: list[list[float]] | None = None
    right: list[list[float]] | None = None
    operation: str | None = None
    vector: list[float] | None = None
    equation: str | None = None
    variables: list[str] = field(default_factory=list)
    variable: str | None = None
    lower: str | None = None
    upper: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalculatorRequest":
        return cls(
            mode=str(data.get("mode", "auto")),
            expression=data.get("expression"),
            angle_unit=str(data.get("angle_unit", "rad")),
            value=data.get("value"),
            from_unit=data.get("from_unit"),
            to_unit=data.get("to_unit"),
            matrix=data.get("matrix"),
            left=data.get("left"),
            right=data.get("right"),
            operation=data.get("operation"),
            vector=data.get("vector"),
            equation=data.get("equation"),
            variables=list(data.get("variables", [])),
            variable=data.get("variable"),
            lower=data.get("lower"),
            upper=data.get("upper"),
        )
