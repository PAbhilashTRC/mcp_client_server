
from pydantic import BaseModel

class MCPConfig(BaseModel):
    url: str
    type: str