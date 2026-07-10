
def warn(*args, **kwargs):
    pass
import json
import warnings

from exceptiongroup import catch
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
    def __init__(self):
        self.available_tools: List = [] # new
        self.available_session: types.InitializeResult = None

    async def run(self) -> Dict[str, Any]:
        try:
            with open("C:\\Users\\PAbhilash\\Documents\\FastAPI\\mcp_client\\app\\mcp_client\\mcp_config.json", "r") as file:
                config = json.load(file)
            servers = config.get("mcp_servers", [])
            print(f"Loaded MCP server configuration: {servers}")
            for server in servers:
                url = server.get("url")
                name = server.get("name")
                type_ = server.get("type")
                mode = server.get("mode", "default")
                print(f"Connecting to MCP server: {name} ({type_}) at {url}")
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
                if result:
                    tools = result.get("tools", [])
                    instructions = result.get("instructions", "")
                    openai_tools = self.mcp_tools_to_openai(tools)
                    self.available_tools.extend(openai_tools)
                    # print(f"Instructions from {name}: {instructions}")
                    tool_names = [tool["function"]["name"] for tool in openai_tools]
                    return {"tools": tool_names, "instructions": instructions}
                return {"Error": f"Failed to connect to MCP server: {name} at {url}"}

        except Exception as e:
            print(f"Error occurred: {e}")
            return {"Error": str(e)}

    async def call_func(self, parsed_result):
        for call in parsed_result:
            func_name = call.get("name")
            params = call.get("parameters", {})

            for tool_call in self.available_tools:
                if tool_call["name"] == func_name:
                    session = self.tool_to_session[func_name]
                    result = await session.call_tool(func_name, arguments=params)
                    print("Results from DB : ", result.content[0].text)
                else:
                    print(f"Unknown function: {func_name}, {params}")

    async def connect_to_sse_server(self, url: str) -> None:
        """Connect to a single MCP server."""
        try:
            # async with streamable_http_client(url) as (
            #     read_stream,
            #     write_stream
            # ):
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
    