import json

from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.llm.open_ai import AzureOpenAIChatClient
from app.model import UserQuery
from .mcp_client.mcp_client import OpenAiMCPClient

app = FastAPI()
CONFIG_PATH = get_settings().mcp_config_path

@asynccontextmanager
async def lifespan(app: FastAPI):
    client = OpenAiMCPClient(CONFIG_PATH)
    openai_client = AzureOpenAIChatClient(get_settings())
    app.state.mcp_client = client
    app.state.openai_client = openai_client

    app.state.mcp_results = await client.run()
    if "Error" in app.state.mcp_results:
        print("MCP connection failed:", app.state.mcp_results["Error"])

    try:
        yield
    finally:
        await client.close()
app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return app.state.mcp_results

@app.post("/user_query")
async def handle_user_query(user_query: UserQuery):
    # Process the user query and interact with MCP tools

    system_prompt = f"""You may use the available MCP tools when needed.

    Follow the MCP server instructions below when they apply. Treat them as
    system-level operational guidance for their respective tools.

    {app.state.mcp_results.get("instructions", {})}

    After receiving tool results, produce a concise answer matching the required
    JSON schema. Return valid JSON only; do not wrap it in Markdown fences.
    """

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_query.query,
        },
    ]
    answer_text = await app.state.openai_client.complete_with_tools(
            messages=messages,
            tools=app.state.mcp_results["tools"],
            tool_executor=app.state.mcp_client.call_func,
        )
    response = json.loads(answer_text)
    return JSONResponse(status_code=200, content=response)