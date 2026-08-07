from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolInvocation:
    name: str
    request: dict


class CalculatorRouter:
    """Recognize safe, obvious calculation requests before the LLM is called."""

    _unit_pattern = re.compile(
        r"(?P<value>[+-]?\d+(?:\.\d+)?)\s*"
        r"(?P<from>公里|千米|米|厘米|毫米|英寸|英尺|km/h|m/s|km|m|cm|mm|kg|g|degC|degF|摄氏度|华氏度|升|毫升|秒|分钟|小时|天|KB|MB|GB|GiB)\s*"
        r"(?:换算成|转换为|转为|换成|等于)\s*"
        r"(?P<to>公里|千米|米|厘米|毫米|英寸|英尺|km/h|m/s|km|m|cm|mm|kg|g|degC|degF|摄氏度|华氏度|升|毫升|秒|分钟|小时|天|KB|MB|GB|GiB)",
        re.IGNORECASE,
    )

    @classmethod
    def route(cls, query: str) -> ToolInvocation | None:
        text = str(query).strip()
        if not text:
            return None

        unit_match = cls._unit_pattern.search(text)
        if unit_match:
            value = float(unit_match.group("value"))
            if value.is_integer():
                value = int(value)
            return ToolInvocation(
                "calculator",
                {
                    "mode": "unit",
                    "value": value,
                    "from_unit": unit_match.group("from"),
                    "to_unit": unit_match.group("to"),
                },
            )

        equation = cls._extract_equation(text)
        if equation:
            variables = sorted(set(re.findall(r"\b[A-Za-z_]\w*\b", equation)))
            return ToolInvocation(
                "calculator",
                {"mode": "equation", "equation": equation, "variables": variables},
            )

        scientific = cls._extract_scientific(text)
        if scientific:
            return ToolInvocation("calculator", scientific)

        expression = cls._extract_arithmetic(text)
        has_calculation_cue = any(word in text for word in ("计算", "算一下", "算出", "等于多少", "结果是多少"))
        if expression and (has_calculation_cue or any(operator in expression for operator in "+-*/%^")):
            return ToolInvocation(
                "calculator",
                {"mode": "arithmetic", "expression": expression},
            )
        return None

    @staticmethod
    def _extract_equation(text: str) -> str | None:
        if "=" not in text or not any(word in text for word in ("方程", "求解", "解")):
            return None
        match = re.search(r"(?P<equation>[A-Za-z][A-Za-z0-9_+\-*/%^().=\s]*)", text)
        if not match:
            return None
        equation = re.sub(r"\s+", " ", match.group("equation")).strip()
        return equation if "=" in equation else None

    @staticmethod
    def _extract_arithmetic(text: str) -> str | None:
        normalized = text
        for source, target in (
            ("乘以", "*"),
            ("乘", "*"),
            ("×", "*"),
            ("✕", "*"),
            ("✖", "*"),
            ("除以", "/"),
            ("除", "/"),
            ("÷", "/"),
            ("加", "+"),
            ("减去", "-"),
            ("减", "-"),
        ):
            normalized = normalized.replace(source, target)
        match = re.search(r"(?P<expression>[0-9][0-9eE.+\-*/%^()\s]*)", normalized)
        if not match:
            return None
        expression = re.sub(r"\s+", "", match.group("expression"))
        return expression or None

    @staticmethod
    def _extract_scientific(text: str) -> dict | None:
        match = re.search(
            r"\b(?P<function>asin|acos|atan|sin|cos|tan|sqrt|log|ln|exp|abs)\s*"
            r"(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(?P<degree>度|degrees?)?",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        function = match.group("function").lower()
        value = match.group("value")
        request = {"mode": "arithmetic", "expression": f"{function}({value})"}
        if match.group("degree") and function in {"sin", "cos", "tan", "asin", "acos", "atan"}:
            request["angle_unit"] = "deg"
        return request
