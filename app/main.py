from fastapi import FastAPI
from .mcp_client.mcp_client import OpenAi_MCP_Client

app = FastAPI()
mcp_client = OpenAi_MCP_Client()
@app.get("/")
async def root():
    mcp_results = await mcp_client.run()
    return {"message": mcp_results}

@app.get("/user_query")
async def user_query():
    # Implementation for handling user queries
    pass