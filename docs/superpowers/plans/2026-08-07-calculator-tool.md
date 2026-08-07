# LocalMind 高级计算 Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** 在 `G:\trial_project\004\tools\calculator` 创建一个安全、模块化、可供 Agent 调用的高级计算工具，覆盖科学计算、单位换算、矩阵运算、方程求解和符号计算。

**Architecture:** 使用统一的 `CalculatorTool.run(request)` 入口，根据 `mode` 或自动识别请求，委托给独立计算模块。所有结果和错误都通过结构化数据返回；算术表达式使用受限 AST 白名单，符号表达式使用 SymPy 的受限解析选项，工具不执行任意 Python 代码、不访问文件和网络。

**Tech Stack:** Python 3.10+、标准库 `ast`/`math`、NumPy、Pint、SymPy、pytest。

## Global Constraints

- 工具目录固定为 `G:\trial_project\004\tools\calculator`。
- 不允许使用 `eval`、`exec` 或动态导入执行用户输入。
- 计算失败必须返回统一错误结构，不向调用方泄露堆栈。
- 表达式长度、AST 深度、矩阵大小和符号运算规模必须有限制。
- 原有 LocalMind LLM、Embedding、Chroma 业务代码不直接改动。
- 每个任务先写失败测试，再写最小实现，最后运行针对性测试和全量测试。

## File Map

- Create: `tools/__init__.py` — 工具包标记。
- Create: `tools/calculator/__init__.py` — 导出计算工具公共接口。
- Create: `tools/calculator/schemas.py` — 请求、结果、错误的数据结构和序列化。
- Create: `tools/calculator/core.py` — 受限 AST 算术/科学表达式执行器。
- Create: `tools/calculator/scientific.py` — 角度单位和科学函数适配。
- Create: `tools/calculator/units.py` — Pint 单位换算适配和别名。
- Create: `tools/calculator/matrix.py` — NumPy 矩阵运算和线性方程组。
- Create: `tools/calculator/equations.py` — SymPy 方程求解。
- Create: `tools/calculator/symbolic.py` — SymPy 化简、求导和积分。
- Create: `tools/calculator/tool.py` — 自动识别和统一 Tool 入口。
- Modify: `requirements.txt` — 增加 `numpy`、`pint`、`sympy` 的显式依赖声明。
- Create: `tests/test_calculator_core.py` — 核心表达式、安全边界和错误测试。
- Create: `tests/test_calculator_units.py` — 单位换算测试。
- Create: `tests/test_calculator_matrix.py` — 矩阵测试。
- Create: `tests/test_calculator_symbolic.py` — 方程和符号计算测试。
- Create: `tests/test_calculator_tool.py` — 统一入口和返回结构测试。
- Modify: `README.md` — 增加计算 Tool 的调用示例和支持范围。

### Task 1: 建立统一数据结构和核心安全表达式计算

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/calculator/__init__.py`
- Create: `tools/calculator/schemas.py`
- Create: `tools/calculator/core.py`
- Create: `tests/test_calculator_core.py`

**Interfaces:**
- `CalculatorRequest.from_dict(data: dict) -> CalculatorRequest`
- `CalculatorResult.to_dict() -> dict`
- `CalculatorError(code: str, message: str)`
- `evaluate_expression(expression: str, *, angle_unit: str = "rad") -> CalculatorResult`

- [ ] **Step 1: Write the failing tests**

```python
def test_evaluates_arithmetic_with_parentheses_and_power():
    result = evaluate_expression("(2 + 3) ** 2")
    assert result.success is True
    assert result.result == "25"


def test_rejects_function_calls_not_in_allowlist():
    result = evaluate_expression("__import__('os').system('whoami')")
    assert result.success is False
    assert result.error.code == "unsupported_syntax"


def test_returns_structured_division_by_zero_error():
    result = evaluate_expression("1 / 0")
    assert result.success is False
    assert result.error.code == "division_by_zero"
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
.\.venv_gpu\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_calculator_core.py
```

Expected: FAIL because the calculator modules do not exist.

- [ ] **Step 3: Implement the minimum safe AST evaluator**

Allow only `Expression`, numeric constants, unary `+/-`, binary `+ - * / // % **`, parentheses represented by AST grouping, and a fixed function/constant map. Reject names not in the map, all attribute access, comprehensions, assignments, imports, strings, and calls outside the allowlist. Enforce expression length `<= 500`, AST depth `<= 30`, and exponent absolute value `<= 1000`.

- [ ] **Step 4: Run the focused tests and confirm they pass**

Run the same command. Expected: all core tests pass.

- [ ] **Step 5: Add core edge-case tests and implementation**

Cover scientific notation, modulo, floor division, negative numbers, unknown names, malformed syntax, oversized input, and finite-result validation. Keep every failure in `CalculatorResult` instead of raising raw exceptions.

- [ ] **Step 6: Run the focused tests again**

Expected: all core tests pass with no unhandled exceptions.

### Task 2: Add scientific functions and angle handling

**Files:**
- Create: `tools/calculator/scientific.py`
- Modify: `tools/calculator/core.py`
- Modify: `tests/test_calculator_core.py`

**Interfaces:**
- `SCIENTIFIC_FUNCTIONS: dict[str, Callable]`
- `evaluate_expression(expression: str, *, angle_unit: Literal["rad", "deg"] = "rad") -> CalculatorResult`

- [ ] **Step 1: Add failing tests**

```python
def test_supports_common_scientific_functions():
    assert evaluate_expression("sqrt(16)").result == "4"
    assert evaluate_expression("log(100, 10)").result == "2"


def test_supports_degree_trigonometry():
    result = evaluate_expression("sin(90)", angle_unit="deg")
    assert result.success is True
    assert abs(float(result.result) - 1.0) < 1e-10
```

- [ ] **Step 2: Run tests to confirm failure**

Expected: FAIL because scientific function names are not registered.

- [ ] **Step 3: Implement the allowlisted scientific function adapter**

Implement `sqrt`, `abs`, `round`, `sin`, `cos`, `tan`, inverse trig functions, `log`, `ln`, and `exp`. Convert degree arguments to radians before trig functions and convert inverse trig results back to degrees when requested. Map math domain errors to `math_domain_error`.

- [ ] **Step 4: Run focused tests**

Expected: all scientific tests pass.

### Task 3: Add unit conversion

**Files:**
- Modify: `requirements.txt`
- Create: `tools/calculator/units.py`
- Create: `tests/test_calculator_units.py`

**Interfaces:**
- `convert_unit(value: float, from_unit: str, to_unit: str) -> CalculatorResult`

- [ ] **Step 1: Add failing tests**

```python
def test_converts_length_with_aliases():
    result = convert_unit(5, "公里", "m")
    assert result.success is True
    assert result.result == "5000"


def test_converts_temperature():
    result = convert_unit(100, "degC", "degF")
    assert result.success is True
    assert result.result == "212"


def test_rejects_incompatible_units():
    result = convert_unit(1, "m", "kg")
    assert result.success is False
    assert result.error.code == "incompatible_units"
```

- [ ] **Step 2: Run focused tests and confirm failure**

Expected: FAIL because the adapter does not exist.

- [ ] **Step 3: Add Pint adapter and aliases**

Register aliases for Chinese and English common names across length, area, volume, mass, time, speed, temperature, and data size. Format integral values without a trailing `.0`; preserve a bounded decimal representation for non-integral results.

- [ ] **Step 4: Run unit tests**

Expected: all unit tests pass.

### Task 4: Add matrix operations

**Files:**
- Modify: `requirements.txt`
- Create: `tools/calculator/matrix.py`
- Create: `tests/test_calculator_matrix.py`

**Interfaces:**
- `matrix_add(left: list[list[float]], right: list[list[float]]) -> CalculatorResult`
- `matrix_subtract(left: list[list[float]], right: list[list[float]]) -> CalculatorResult`
- `matrix_multiply(left: list[list[float]], right: list[list[float]]) -> CalculatorResult`
- `matrix_transpose(matrix: list[list[float]]) -> CalculatorResult`
- `matrix_determinant(matrix: list[list[float]]) -> CalculatorResult`
- `matrix_inverse(matrix: list[list[float]]) -> CalculatorResult`
- `solve_linear_system(matrix: list[list[float]], vector: list[float]) -> CalculatorResult`

- [ ] **Step 1: Add failing tests**

Test 2×2 multiplication, transpose, determinant, inverse, linear-system solution, and a dimension mismatch returning `dimension_mismatch`.

- [ ] **Step 2: Run focused tests and confirm failure**

Expected: FAIL because matrix functions do not exist.

- [ ] **Step 3: Implement NumPy adapter**

Validate rectangular numeric matrices and limit each dimension to `32`. Return JSON-compatible nested lists and floats. Map singular matrices to `singular_matrix` and invalid shapes to `dimension_mismatch`.

- [ ] **Step 4: Run matrix tests**

Expected: all matrix tests pass.

### Task 5: Add equations and symbolic operations

**Files:**
- Modify: `requirements.txt`
- Create: `tools/calculator/equations.py`
- Create: `tools/calculator/symbolic.py`
- Create: `tests/test_calculator_symbolic.py`

**Interfaces:**
- `solve_equation(equation: str, variables: list[str]) -> CalculatorResult`
- `simplify_expression(expression: str) -> CalculatorResult`
- `differentiate_expression(expression: str, variable: str) -> CalculatorResult`
- `integrate_expression(expression: str, variable: str, lower: str | None = None, upper: str | None = None) -> CalculatorResult`

- [ ] **Step 1: Add failing tests**

```python
def test_solves_quadratic_equation():
    result = solve_equation("x**2 - 5*x + 6 = 0", ["x"])
    assert result.success is True
    assert result.result == ["2", "3"]


def test_differentiates_expression():
    result = differentiate_expression("x**3 + x", "x")
    assert result.success is True
    assert result.result == "3*x**2 + 1"


def test_rejects_non_identifier_variable_name():
    result = differentiate_expression("x + 1", "__import__('os')")
    assert result.success is False
    assert result.error.code == "invalid_variable"
```

- [ ] **Step 2: Run focused tests and confirm failure**

Expected: FAIL because symbolic modules do not exist.

- [ ] **Step 3: Implement restricted SymPy adapters**

Validate variable identifiers with `str.isidentifier()` and reject dunder names. Use explicit local symbols and `parse_expr` with transformations limited to standard mathematical syntax; do not expose Python builtins. Normalize equations by replacing one `=` with an equality expression. Limit expression length to `500` and variable count to `8`.

- [ ] **Step 4: Run symbolic tests**

Expected: all equation, simplify, derivative, and integral tests pass.

### Task 6: Add the unified Agent Tool interface

**Files:**
- Create: `tools/calculator/tool.py`
- Modify: `tools/calculator/__init__.py`
- Create: `tests/test_calculator_tool.py`

**Interfaces:**
- `class CalculatorTool:`
- `CalculatorTool.name == "calculator"`
- `CalculatorTool.description: str`
- `CalculatorTool.schema() -> dict`
- `CalculatorTool.run(request: dict | CalculatorRequest) -> dict`
- `calculator_tool = CalculatorTool()`

- [ ] **Step 1: Add failing tests**

Test explicit modes `arithmetic`, `unit`, `matrix`, `equation`, `symbolic`; test `auto` mode for arithmetic and equation; assert every result contains `success`, `mode`, `expression`, `result`, `steps`, and `error`; assert unknown mode returns `unsupported_mode`.

- [ ] **Step 2: Run focused tests and confirm failure**

Expected: FAIL because `CalculatorTool` does not exist.

- [ ] **Step 3: Implement dispatch and schema**

Dispatch explicit mode to the corresponding module. For `auto`, recognize structured keys first, then use equation syntax for an equality containing a variable, and otherwise use the safe expression evaluator. Expose a JSON-like schema describing mode, expression, value, units, matrix, equation, and variables.

- [ ] **Step 4: Run tool tests**

Expected: all dispatch and schema tests pass.

### Task 7: Documentation, dependency installation, and full verification

**Files:**
- Modify: `README.md`
- Modify: `requirements.txt`

- [ ] **Step 1: Add README usage examples**

Document direct Python calls for arithmetic, unit conversion, matrix operation, and equation solving. Explain that the tool does not automatically become available to the LLM until an Agent orchestration layer registers `calculator_tool.schema()` and executes `calculator_tool.run()`.

- [ ] **Step 2: Install declared dependencies in the GPU environment**

Run:

```powershell
.\.venv_gpu\Scripts\python.exe -m pip install -r requirements.txt
```

- [ ] **Step 3: Run calculator tests**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
.\.venv_gpu\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_calculator_core.py tests/test_calculator_units.py tests/test_calculator_matrix.py tests/test_calculator_symbolic.py tests/test_calculator_tool.py
```

Expected: all calculator tests pass.

- [ ] **Step 4: Run the complete regression suite**

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:QT_QPA_PLATFORM='offscreen'
.\.venv_gpu\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Expected: all existing and new tests pass.

- [ ] **Step 5: Run a real smoke test**

Execute the public interface with these requests and verify structured output:

```python
calculator_tool.run({"mode": "arithmetic", "expression": "123456789 * 987654321"})
calculator_tool.run({"mode": "unit", "value": 5, "from_unit": "km", "to_unit": "m"})
calculator_tool.run({"mode": "equation", "equation": "x**2 - 5*x + 6 = 0", "variables": ["x"]})
```

Expected results are `121932631112635269`, `5000`, and roots `2`/`3` respectively.
