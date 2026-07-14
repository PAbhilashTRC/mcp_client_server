"""MCP client with optional OAuth authorization for SSE and Streamable HTTP.

Example mcp_config.json entry:
{
  "name": "protected-server",
  "url": "http://localhost:8000/mcp",
  "type": "http",
  "mode": "streamable",
  "authorization": {"enabled": true, "callback_port": 3030}
}
"""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import socketserver
import threading
import webbrowser
from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import parse_qs, urlsplit, urlunsplit

import httpx
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client._transport import ReadStream, WriteStream
from mcp.client.auth import AuthorizationCodeResult, OAuthClientProvider, TokenStorage
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken
from mcp.shared.message import SessionMessage
import mcp_types as types
from fastapi.encoders import jsonable_encoder

load_dotenv()


class InMemoryTokenStorage(TokenStorage):
    """Token storage for one process. Replace for persistent logins."""

    def __init__(self) -> None:
        self._tokens: OAuthToken | None = None
        self._client_info: OAuthClientInformationFull | None = None

    async def get_tokens(self) -> OAuthToken | None:
        return self._tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self._tokens = tokens

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return self._client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self._client_info = client_info


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Receive the authorization-code redirect on localhost."""

    callback_data: dict[str, str | None]
    callback_received: threading.Event

    def do_GET(self) -> None:  # noqa: N802 - HTTPServer callback name
        parameters = parse_qs(urlsplit(self.path).query)
        self.callback_data["code"] = parameters.get("code", [None])[0]
        self.callback_data["state"] = parameters.get("state", [None])[0]
        self.callback_data["iss"] = parameters.get("iss", [None])[0]
        self.callback_data["error"] = parameters.get("error", [None])[0]
        self.callback_received.set()

        success = self.callback_data["code"] is not None
        self.send_response(200 if success else 400)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        message = "Authorization successful. You can close this window." if success else "Authorization failed. Return to the application."
        self.wfile.write(f"<h1>{message}</h1>".encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        """Do not print one access-log line for each OAuth redirect."""


class CallbackServer:
    def __init__(self, port: int) -> None:
        self.port = port
        self.callback_data: dict[str, str | None] = {"code": None, "state": None, "iss": None, "error": None}
        self.callback_received = threading.Event()
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        parent = self

        class Handler(OAuthCallbackHandler):
            callback_data = parent.callback_data
            callback_received = parent.callback_received

        self.server = HTTPServer(("127.0.0.1", self.port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    async def wait_for_result(self, timeout: float = 300) -> AuthorizationCodeResult:
        received = await asyncio.to_thread(self.callback_received.wait, timeout)
        if not received:
            raise TimeoutError("Timed out waiting for the OAuth callback")
        if self.callback_data["error"]:
            raise RuntimeError(f"OAuth authorization failed: {self.callback_data['error']}")
        if not self.callback_data["code"]:
            raise RuntimeError("OAuth callback did not contain an authorization code")
        return AuthorizationCodeResult(
            code=self.callback_data["code"],
            state=self.callback_data["state"],
            iss=self.callback_data["iss"],
        )
    
    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)


def authorization_server_url(mcp_url: str) -> str:
    """Remove the conventional MCP endpoint (/mcp or /sse) from a URL."""
    parts = urlsplit(mcp_url)
    path = parts.path.rstrip("/")
    if path.endswith("/mcp") or path.endswith("/sse"):
        path = path.rsplit("/", 1)[0] or "/"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


class ToolDefinition(TypedDict):
    name: str
    description: str
    input_schema: dict[str, Any]

class OpenAiMCPClient:
    """Keeps authenticated MCP sessions open until ``close`` is called."""

    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)
        self.available_tools: list[dict[str, Any]] = []
        self.tool_to_session: dict[str, ClientSession] = {}
        self._resources = AsyncExitStack()

    def _oauth_provider(self, url: str, auth_config: dict[str, Any]) -> OAuthClientProvider:
        port = int(auth_config.get("callback_port", 3030))
        callback_server = CallbackServer(port)

        async def redirect_handler(authorization_url: str) -> None:
            print(f"Opening browser for authorization: {authorization_url}")
            webbrowser.open(authorization_url)

        async def callback_handler() -> AuthorizationCodeResult:
            # Start only when an authorization code is actually needed. A stored
            # token/refresh token therefore does not leave an unused server open.
            callback_server.start()
            try:
                return await callback_server.wait_for_result()
            finally:
                callback_server.stop()

        metadata = OAuthClientMetadata.model_validate({
            "client_name": auth_config.get("client_name", "OpenAI MCP Client"),
            "redirect_uris": [f"http://127.0.0.1:{port}/oauth2callback"],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        })
        return OAuthClientProvider(
            server_url=authorization_server_url(url),
            client_metadata=metadata,
            storage=InMemoryTokenStorage(),
            redirect_handler=redirect_handler,
            callback_handler=callback_handler,
            client_metadata_url=auth_config.get("client_metadata_url"),
        )
        
    async def run(self) -> dict[str, Any]:
        """Connect to configured servers and return their OpenAI tool definitions."""
        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
            instructions_by_server: dict[str, str] = {}
            for server_name, server_config in config.get("mcp_servers", {}).items():
                url = server_config.get("url")
                mode = server_config.get("mode", "streamable")
                if not url or server_config.get("type") != "http":
                    raise ValueError(f"Invalid HTTP MCP configuration for {server_name}")

                auth_config = server_config.get("authorization", {})
                auth = self._oauth_provider(url, auth_config) if auth_config.get("enabled", False) else None
                session, tools_result, instructions = await self.connect(url, mode, auth)
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
        
    async def connect(self, url: str, mode: str, auth: OAuthClientProvider | None) -> tuple[ClientSession, types.ListToolsResult, str]:
        if mode == "sse":
            read_stream, write_stream = await self._resources.enter_async_context(sse_client(url, auth=auth, timeout=60.0))
        else:
            http_client = await self._resources.enter_async_context(httpx.AsyncClient(auth=auth, follow_redirects=True))
            read_stream, write_stream = await self._resources.enter_async_context(streamable_http_client(url, http_client=http_client))
        session = await self._resources.enter_async_context(ClientSession(read_stream, write_stream))
        initialize_result = await session.initialize()
        return session, await session.list_tools(), initialize_result.instructions or ""

    async def call_func(self, name: str, parameters: dict[str, Any]) -> list[Any]:
        """Call OpenAI-style function calls: {name: ..., parameters: {...}}."""
        results = []
        params = parameters
        session = self.tool_to_session.get(name)
        if not session:
            raise ValueError(f"Unknown MCP tool: {name}")
        raw_results = await session.call_tool(name, arguments=params)
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
