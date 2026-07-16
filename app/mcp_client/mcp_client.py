
def warn(*args, **kwargs):
    pass
from contextlib import AsyncExitStack
import json
import warnings

from pathlib import Path
from fastapi.encoders import jsonable_encoder

warnings.warn = warn
warnings.filterwarnings('ignore')

from typing import Any, Dict, List, TypedDict
import os
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
import mcp_types as types
load_dotenv()
    
class OpenAiMCPClient():
    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self.available_tools: List[dict[str, Any]] = [] # new
        self.tool_to_session: dict[str, ClientSession] = {}
        self._resources = AsyncExitStack()

    async def run(self) -> dict[str, Any]:
        """Connect to configured servers and return their OpenAI tool definitions."""
        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
            instructions_by_server: dict[str, str] = {}
            for server_name, server_config in config.get("mcp_servers", {}).items():
                if not (server_config.get("type") == "http" or server_config.get("type") == "stdio"):
                    raise ValueError(f"Invalid MCP configuration for {server_name}")
                if server_config.get("type") == "http":
                    url = server_config.get("url")
                    mode = server_config.get("mode", "streamable")
                    session, tools_result, instructions = await self.connect(url, mode)
                elif server_config.get("type") == "stdio":
                    url = None
                    mode = "streamable"
                    session, tools_result, instructions = await self.connect_to_stdio(server_config)
                instructions_by_server[server_name] = instructions
                for tool in tools_result.tools:
                    openai_tool = self.mcp_tools_to_openai([tool])[0]
                    tool_name = openai_tool["function"]["name"]
                    if tool_name in self.tool_to_session:
                        raise ValueError(f"Duplicate MCP tool name: {tool_name}")
                    self.available_tools.append(openai_tool)
                    self.tool_to_session[tool_name] = session
                print(f"Connected to {server_name}: {len(tools_result.tools)} tools")
            return {"tools": self.available_tools, "instructions": instructions_by_server}
        except Exception as exc:
            await self.close()
            return {"Error": str(exc)}
        
    async def connect(self, url: str, mode: str) -> tuple[ClientSession, types.ListToolsResult, str]:
        if mode == "sse":
            read_stream, write_stream = await self._resources.enter_async_context(sse_client(url, timeout=60.0))
        else:
            read_stream, write_stream = await self._resources.enter_async_context(streamable_http_client(url))
        session = await self._resources.enter_async_context(ClientSession(read_stream, write_stream))
        initialize_result = await session.initialize()
        return session, await session.list_tools(), initialize_result.instructions or ""
    
    async def connect_to_stdio(self, server_config: dict) -> tuple[ClientSession, types.ListToolsResult, str]:
        server_params = StdioServerParameters(**server_config)
        read_stream, write_stream = await self._resources.enter_async_context(stdio_client(server_params))
        session = await self._resources.enter_async_context(ClientSession(read_stream, write_stream))
        initialize_result = await session.initialize()
        return session, await session.list_tools(), initialize_result.instructions or ""

    async def call_func(self, name: str, parameters: dict[str, Any]) -> list[Any]:
        """Call OpenAI-style function calls: {name: ..., parameters: {...}}."""
        results = []
        session = self.tool_to_session.get(name)
        if not session:
            raise ValueError(f"Unknown MCP tool: {name}")
        raw_results = await session.call_tool(name, arguments=parameters)
        results.append(jsonable_encoder(raw_results))
        return results

    async def close(self) -> None:
        """Close sessions and network transports after all tool calls are complete."""
        await self._resources.aclose()
        
    @staticmethod
    def mcp_tools_to_openai(tools: list[types.Tool]) -> list[dict[str, Any]]:
        return [{"type": "function", "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        }} for tool in tools]
    