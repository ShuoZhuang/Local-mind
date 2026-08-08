from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.models import MCPServerDefinition


T = TypeVar("T")


class MCPClientError(RuntimeError):
    """A connection or protocol failure reported in LocalMind language."""


@dataclass(frozen=True)
class MCPToolInfo:
    name: str
    title: str | None
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class MCPCallResult:
    success: bool
    content: list[str]
    structured_content: dict[str, Any] | None = None
    is_error: bool = False
    error: str | None = None


class MCPClientService:
    """Run one trusted local stdio MCP operation in an isolated session."""

    def discover(self, server: MCPServerDefinition) -> list[MCPToolInfo]:
        return asyncio.run(self._with_session(server, self._discover))

    def call_tool(
        self,
        server: MCPServerDefinition,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPCallResult:
        try:
            return asyncio.run(
                self._with_session(
                    server,
                    lambda session: self._call(session, tool_name, arguments or {}),
                )
            )
        except Exception as error:
            return MCPCallResult(
                success=False,
                content=[],
                is_error=True,
                error=self._format_error(server, error),
            )

    async def _with_session(
        self,
        server: MCPServerDefinition,
        operation: Callable[[ClientSession], Awaitable[T]],
    ) -> T:
        if not server.command.strip():
            raise MCPClientError("MCP 服务命令不能为空")
        parameters = StdioServerParameters(
            command=server.command,
            args=list(server.args),
            cwd=server.cwd,
            env={**os.environ, **server.env},
        )
        try:
            async with stdio_client(parameters) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    return await operation(session)
        except MCPClientError:
            raise
        except Exception as error:
            raise MCPClientError(self._format_error(server, error)) from error

    @staticmethod
    async def _discover(session: ClientSession) -> list[MCPToolInfo]:
        response = await session.list_tools()
        return [
            MCPToolInfo(
                name=str(tool.name),
                title=str(tool.title) if tool.title else None,
                description=str(tool.description or "未提供描述"),
                input_schema=dict(tool.input_schema or {}),
            )
            for tool in response.tools
        ]

    @staticmethod
    async def _call(
        session: ClientSession,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> MCPCallResult:
        response = await session.call_tool(tool_name, arguments)
        content = [
            str(getattr(item, "text", item))
            for item in getattr(response, "content", [])
        ]
        structured_content = getattr(response, "structured_content", None)
        if structured_content is not None:
            structured_content = dict(structured_content)
        is_error = bool(getattr(response, "is_error", False))
        return MCPCallResult(
            success=not is_error,
            content=content,
            structured_content=structured_content,
            is_error=is_error,
            error="\n".join(content) if is_error else None,
        )

    @staticmethod
    def _format_error(server: MCPServerDefinition, error: Exception) -> str:
        if isinstance(error, FileNotFoundError):
            return f"无法启动 MCP 服务命令“{server.command}”：命令不存在或不可执行。"
        message = str(error).strip()
        if server.command in message:
            return message
        detail = message or error.__class__.__name__
        return f"MCP 服务“{server.name}”连接失败：{detail}"
