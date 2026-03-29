"""
TRIL MCP Server
Exposes generate_truck_safe_route as an MCP tool over stdio.
Will Graham calls this via OpenClaw's MCP client.
"""

from __future__ import annotations

import asyncio
import json
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from .mcp_tool import MCP_TOOL_DEFINITION, generate_truck_safe_route

logger = logging.getLogger("tril.mcp_server")

server = Server("tril", version="0.1.0", instructions="Truck-safe routing with constraint validation and HOS analysis")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name=MCP_TOOL_DEFINITION["name"],
            description=MCP_TOOL_DEFINITION["description"],
            inputSchema=MCP_TOOL_DEFINITION["input_schema"],
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name != "generate_truck_safe_route":
        raise ValueError(f"Unknown tool: {name}")

    result = generate_truck_safe_route(
        origin=arguments["origin"],
        destination=arguments["destination"],
        stops=arguments.get("stops"),
        vehicle_profile=arguments.get("vehicle_profile"),
        hos=arguments.get("hos"),
        preferences_override=arguments.get("preferences_override"),
    )

    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run():
    """Entry point for the MCP server."""
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
    asyncio.run(main())


if __name__ == "__main__":
    run()
