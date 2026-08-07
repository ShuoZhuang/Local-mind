# LocalMind 高级计算 Tool 设计规格

## 目标

在项目根目录创建独立的 `tools/calculator` 计算工具，为后续 Agent 提供一个统一、可测试、安全的计算能力入口。第一版同时覆盖科学计算、单位换算、矩阵运算、方程求解和符号计算。

## 用户调用方式

工具提供统一入口：

```python
from tools.calculator.tool import calculator_tool

result = calculator_tool.run({
    "mode": "auto",
    "expression": "123456789 * 987654321",
})
```

返回统一结构：

```python
{
    "success": True,
    "mode": "arithmetic",
    "expression": "123456789 * 987654321",
    "result": "121932631112635269",
    "steps": [],
    "error": None,
}
```

失败时不抛出给 Agent 的异常，而是返回：

```python
{
    "success": False,
    "mode": "arithmetic",
    "expression": "1 / 0",
    "result": None,
    "steps": [],
    "error": {"code": "division_by_zero", "message": "除数不能为 0"},
}
```

## 能力范围

### 1. 科学计算

支持数字、科学计数法、括号、正负号、四则运算、整除、取模、幂运算和百分号。

支持函数：`sqrt`、`abs`、`round`、`sin`、`cos`、`tan`、`asin`、`acos`、`atan`、`log`、`ln`、`exp`。

支持常量：`pi`、`e`。

三角函数默认使用弧度；调用参数可通过 `angle_unit` 指定为 `rad` 或 `deg`。

### 2. 单位换算

通过结构化参数执行：

```python
{
    "mode": "unit",
    "value": 5,
    "from_unit": "km",
    "to_unit": "m",
}
```

第一版支持长度、面积、体积、质量、时间、速度、温度、数据大小。单位名称使用稳定的英文标准名，同时允许常见别名，例如 `公里`、`km`、`千米`。

### 3. 矩阵运算

通过结构化参数执行矩阵加法、减法、乘法、转置、行列式、逆矩阵和线性方程组求解。输入必须是二维数字数组，维度不匹配返回结构化错误。

### 4. 方程与符号计算

支持一元/多元方程求解、表达式化简、求导和定积分。符号输入使用 `sympy` 解析，变量名限制为字母、数字和下划线组成的标识符，禁止执行任意代码。

示例：

```python
{
    "mode": "equation",
    "equation": "x**2 - 5*x + 6 = 0",
    "variables": ["x"],
}
```

## 安全边界

- 不使用 Python `eval` 或 `exec` 执行用户表达式。
- 科学计算使用受限 AST 白名单解析器。
- 符号计算只允许受限数学语法和显式变量。
- 限制表达式长度、嵌套深度、矩阵大小和计算超时，避免恶意输入造成资源耗尽。
- 工具不读写文件、不执行系统命令、不联网。

## 目录与模块职责

```text
tools/
└── calculator/
    ├── __init__.py
    ├── schemas.py       # 请求、结果、错误的数据结构
    ├── core.py          # 安全算术和科学表达式解析
    ├── scientific.py    # 角度单位和科学函数适配
    ├── units.py         # 单位注册表和换算
    ├── matrix.py        # 矩阵运算
    ├── equations.py     # 方程求解
    ├── symbolic.py      # 化简、求导、积分
    └── tool.py          # 自动识别和统一 Tool 入口
```

## 依赖

- `sympy`：符号计算、方程、求导、积分。
- `pint`：单位换算。
- `numpy`：矩阵计算。

现有 Agent 的 LLM、Embedding、Chroma 代码不直接改动。后续接入 Agent 时，只通过 `calculator_tool.run()` 调用。

## 测试验收标准

- 四则、括号、幂、百分号、科学计数法和常见函数结果正确。
- 角度制和弧度制结果正确。
- 单位换算和温度换算正确。
- 矩阵合法输入正确，维度错误返回明确错误。
- 方程、求导和积分返回可读结果。
- 除零、未知函数、非法字符、超长表达式和恶意语法均被拒绝。
- 工具所有失败路径均返回统一错误结构，不泄露内部堆栈。
- 项目原有测试保持通过。
