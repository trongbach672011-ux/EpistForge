from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from research_tool.mcp_server import REQUIRED_TOOL_NAMES


def test_mcp_stdio_initialize_and_list_tools() -> None:
    root = Path(__file__).resolve().parents[1]

    async def run() -> set[str]:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "research_tool.mcp_server"],
            cwd=root,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                response = await session.list_tools()
                return {tool.name for tool in response.tools}

    assert asyncio.run(run()) >= REQUIRED_TOOL_NAMES
