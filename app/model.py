
from typing import Any
from pydantic import BaseModel
class AgentStep(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any]

class MCPConfig(BaseModel):
    url: str
    type: str

class UserQuery(BaseModel):
    query: str