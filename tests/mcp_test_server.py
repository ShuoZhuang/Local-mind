from __future__ import annotations

import asyncio

import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server


async def list_tools(_context, _params) -> types.ListToolsResult:
    return types.ListToolsResult(
        tools=[
            types.Tool(
                name="repeat",
                description="返回传入的文字。",
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                output_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            )
        ]
    )


async def call_tool(_context, params: types.CallToolRequestParams) -> types.CallToolResult:
    arguments = params.arguments or {}
    text = str(arguments.get("text", ""))
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)],
        structured_content={"text": text},
    )


server = Server(
    "LocalMind Test Server",
    version="1.0.0",
    on_list_tools=list_tools,
    on_call_tool=call_tool,
)


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="localmind-test-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
