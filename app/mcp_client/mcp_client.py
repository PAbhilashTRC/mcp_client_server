
def warn(*args, **kwargs):
    pass
import json
import warnings

warnings.warn = warn
warnings.filterwarnings('ignore')

from typing import Any, Dict, List, TypedDict
# from langchain_mcp_adapters.tools import load_mcp_tools
import os
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.client.sse import sse_client
import mcp_types as types
load_dotenv()

class ToolDefinition(TypedDict):
    name: str
    description: str
    input_schema: dict
    
class OpenAi_MCP_Client():
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.available_tools: List = [] # new
        self.available_session: types.InitializeResult = None

    async def run(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, "r") as file:
                config = json.load(file)
            servers = config.get("mcp_servers", {})
            print(f"Loaded MCP server configuration: {servers}")
            for server_name, server_config in servers.items():
                url = server_config.get("url")
                type_ = server_config.get("type")
                mode = server_config.get("mode", "default")
                result = []
                print(f"Connecting to MCP server: {server_name} ({type_}) at {url}")
                if not url:
                    return {"Error": "MCP server URL is missing in the configuration."}
                if not type_:
                    return {"Error": "MCP server type is missing in the configuration."}
                if type_ not in ["http"]:
                    return {"Error": f"Unsupported MCP server type: {type_}. Supported types are 'http'."}
                if mode == "sse":
                    result = await self.connect_to_sse_server(url)
                elif mode == "streamable":
                    result = await self.connect_to_streamable_server(url)
                else:
                    result = await self.connect_to_streamable_server(url)
                if(result and "Error" not in result):
                    print(f"Connected to {server_name}: {len(result.get('tools', []))} tools")
                    openai_tool = self.mcp_tools_to_openai(result.get("tools", []))
                    self.available_tools = openai_tool
                    return {"tools": self.available_tools, "instructions": result.get("instructions", "")}
                return {"Error": f"Failed to connect to MCP server: {server_name} at {url}"}

        except Exception as e:
            print(f"Error occurred: {e}")
            return {"Error": str(e)}

    async def call_func(self, func_name:str, args:dict[str, Any]) -> None:
            for tool_call in self.available_tools:
                if tool_call["name"] == func_name:
                    result = await self.available_session.call_tool(func_name, arguments=args)
                    print("Results from DB : ", result.content[0].text)
                    break
                else:
                    print(f"Unknown function: {func_name}, {args}")

    async def connect_to_sse_server(self, url: str) -> None:
        """Connect to a single MCP server."""
        try:
            async with sse_client(url) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    # Initialize the connection
                    self.available_session = await session.initialize()
                    # List available tools
                    tools: types.ListToolsResult = await session.list_tools()
                    instructions = self.available_session.instructions

                    return {"tools": tools.tools, "instructions": instructions}

        except Exception as e:
            print(f"Failed to connect to {url}: {e}")
            return {"Error": str(e)}
        
    async def connect_to_streamable_server(self, url: str) -> None:
        """Connect to a single MCP server."""
        try:
            async with streamable_http_client(url) as (
                read_stream,
                write_stream
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    # Initialize the connection
                    self.available_session = await session.initialize()
                    # List available tools
                    tools: types.ListToolsResult = await session.list_tools()
                    instructions = self.available_session.instructions

                    return {"tools": tools.tools, "instructions": instructions}

        except Exception as e:
            print(f"Failed to connect to {url}: {e}")
            return {"Error": str(e)}
        
    def mcp_tools_to_openai(self, tools: List[types.Tool]) -> List[Dict[str, Any]]:
        """
        Convert MCP Tool objects into OpenAI-compatible tools list
        """

        converted_tools = []

        for tool in tools:
            converted_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.input_schema
                    }
                }
            )

        return converted_tools
    