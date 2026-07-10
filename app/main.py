from contextlib import asynccontextmanager
from fastapi import FastAPI
from .mcp_client.authorized_mcp_client import OpenAiMCPClient
CONFIG_PATH = "C:\\Users\\PAbhilash\\Documents\\FastAPI\\mcp_client\\app\\mcp_client\\mcp_config.json"

@asynccontextmanager
async def lifespan(app: FastAPI):
    client = OpenAiMCPClient(CONFIG_PATH)
    app.state.mcp_client = client

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