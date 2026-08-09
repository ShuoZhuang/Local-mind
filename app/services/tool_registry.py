from __future__ import annotations

from typing import Any

from app.models import MCPServerDefinition, ToolContract, ToolDefinition
from app.services.mcp_client import MCPCallResult, MCPClientService
from app.services.storage import LocalStateStore
from app.services.tool_contracts import contract_for_mcp_tool
from tools.calculator import calculator_tool


class ToolRegistry:
    """The single source of real model-callable tools in LocalMind."""

    def __init__(
        self,
        state: LocalStateStore,
        mcp_client: MCPClientService | None = None,
    ):
        self.state = state
        self.mcp_client = mcp_client or MCPClientService()
        self._mcp_tools: dict[str, ToolDefinition] = {}
        self._mcp_servers: dict[str, MCPServerDefinition] = {
            server.id: server for server in self.state.list_mcp_servers() if server.enabled
        }
        self._server_errors: dict[str, str] = {}
        self._hydrate_mcp_tools_from_snapshot()

    def list_tools(self) -> list[ToolDefinition]:
        return [self._calculator_definition(), *self._mcp_tools.values()]

    def get(self, tool_id: str) -> ToolDefinition | None:
        if tool_id == calculator_tool.name:
            return self._calculator_definition()
        return self._mcp_tools.get(tool_id)

    def refresh_mcp_tools(self) -> list[ToolDefinition]:
        previous_snapshot = self.state.load_mcp_tool_snapshot()
        self._mcp_tools.clear()
        self._mcp_servers.clear()
        self._server_errors.clear()
        refreshed_snapshot: list[dict[str, Any]] = []
        for server in self.state.list_mcp_servers():
            if not server.enabled:
                continue
            self._mcp_servers[server.id] = server
            try:
                discovered = self.mcp_client.discover(server)
            except Exception as error:
                self._server_errors[server.id] = str(error)
                refreshed_snapshot.extend(
                    item
                    for item in previous_snapshot
                    if str(item.get("server_id", "")) == server.id
                )
                continue
            for tool in discovered:
                payload = self._snapshot_payload(server.id, tool.name, tool.title, tool.description, tool.input_schema)
                refreshed_snapshot.append(payload)
                self._register_mcp_tool(server, payload)
        self.state.save_mcp_tool_snapshot(refreshed_snapshot)
        return self.list_tools()

    def reload_display_metadata(self) -> None:
        self._mcp_tools.clear()
        self._hydrate_mcp_tools_from_snapshot()

    def _hydrate_mcp_tools_from_snapshot(self) -> None:
        self._mcp_servers = {
            server.id: server for server in self.state.list_mcp_servers() if server.enabled
        }
        for payload in self.state.load_mcp_tool_snapshot():
            server = self._mcp_servers.get(str(payload.get("server_id", "")))
            if server is not None:
                self._register_mcp_tool(server, payload)

    def _register_mcp_tool(
        self,
        server: MCPServerDefinition,
        payload: dict[str, Any],
    ) -> None:
        tool_name = str(payload.get("tool_name", "")).strip()
        if not tool_name:
            return
        raw_title = str(payload.get("title", tool_name)).strip() or tool_name
        raw_description = str(payload.get("description", "")).strip()
        input_schema = payload.get("input_schema", {})
        if not isinstance(input_schema, dict):
            input_schema = {}
        contract = contract_for_mcp_tool(tool_name, raw_description, input_schema)
        presentation = self.state.get_mcp_tool_display_metadata(server.id, tool_name)
        display_name = presentation.display_name if presentation and presentation.display_name else raw_title
        display_description = presentation.description if presentation and presentation.description else raw_description
        tool_id = self.mcp_tool_id(server.id, tool_name)
        self._mcp_tools[tool_id] = ToolDefinition(
            id=tool_id,
            name=display_name,
            category="MCP",
            description=display_description,
            capabilities=("MCP", "stdio"),
            enabled=True,
            icon_text="↗",
            kind="mcp",
            source=server.name,
            input_schema=input_schema,
            raw_name=raw_title,
            raw_description=raw_description,
            last_error=None if contract.configured else "Tool contract is not configured",
            contract=contract,
        )

    @staticmethod
    def _snapshot_payload(
        server_id: str,
        tool_name: str,
        title: str | None,
        description: str | None,
        input_schema: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "server_id": server_id,
            "tool_name": str(tool_name),
            "title": str(title or tool_name),
            "description": str(description or ""),
            "input_schema": dict(input_schema or {}),
        }

    def server_errors(self) -> dict[str, str]:
        return dict(self._server_errors)

    def call(self, tool_id: str, arguments: dict[str, Any] | None = None):
        definition = self.get(tool_id)
        if definition is None:
            raise KeyError(f"Unknown tool: {tool_id}")
        if not definition.contract.configured:
            raise RuntimeError(f"Tool contract is not configured: {tool_id}")
        if tool_id == calculator_tool.name:
            return calculator_tool.run(arguments or {"mode": "arithmetic", "expression": "2 + 2"})
        server, tool_name = self._mcp_target(tool_id)
        return self.mcp_client.call_tool(server, tool_name, arguments or {})

    @staticmethod
    def mcp_tool_id(server_id: str, tool_name: str) -> str:
        return f"mcp:{server_id}:{tool_name}"

    @staticmethod
    def _calculator_definition() -> ToolDefinition:
        schema = calculator_tool.schema()
        return ToolDefinition(
            id=calculator_tool.name,
            name="高级计算器",
            category="计算",
            description=calculator_tool.description,
            capabilities=("算术", "三角函数", "对数", "矩阵", "方程", "单位换算"),
            enabled=True,
            icon_text="∑",
            recent_calls=("sin(30°) + 125 × 8", "det([[1,2],[3,4]])", "log10(1000)"),
            kind="tool",
            source="LocalMind",
            input_schema=dict(schema.get("parameters", {})),
            contract=ToolContract(
                purpose="执行经过程序校验的科学计算、单位换算、矩阵、方程和符号计算。",
                use_when=("用户明确要求计算、换算、求解方程或符号运算。",),
                avoid_when=("用户只是闲聊、查询事实或需要外部实时数据。",),
                intent_keywords=("计算", "算", "等于", "换算", "方程", "矩阵", "sin", "cos", "log"),
                parameter_rules=("必须符合 calculator schema；不要执行任意 Python 代码。",),
                examples=("123 * 456", "sin(30)",),
                recovery_hint="计算参数不完整时说明缺少字段，不要猜测数值。",
            ),
        )

    def _mcp_target(self, tool_id: str) -> tuple[MCPServerDefinition, str]:
        if not tool_id.startswith("mcp:"):
            raise KeyError(f"未注册的工具: {tool_id}")
        _prefix, server_id, tool_name = tool_id.split(":", 2)
        server = self._mcp_servers.get(server_id)
        if server is None:
            raise KeyError(f"MCP 工具未发现或服务未启用: {tool_id}")
        return server, tool_name
