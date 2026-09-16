from typing import Any, Literal
from pydantic import BaseModel, Field

class AgentMessage(BaseModel):
    message: str = Field(min_length=1,max_length=1000)

class AgentConfirmation(BaseModel):
    confirmation_token: str = Field(min_length=20,max_length=200)

class AgentResponse(BaseModel):
    type: Literal["answer","confirmation_required","action_completed","cancelled","error"]
    message: str
    data: Any = None
    suggested_navigation: str | None = None
    action: str | None = None
    confirmation_token: str | None = None
    preview: dict[str,Any] | None = None
