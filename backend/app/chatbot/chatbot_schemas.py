"""Contrats publics du chatbot, sans identifiant utilisateur fourni par le client."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class ChatRequest(BaseModel):
    message: str = Field(min_length=1,max_length=1000)
    confirm: bool = False

class SuggestedAction(BaseModel):
    label: str
    path: str | None = None
    message: str | None = None

class ChatResponse(BaseModel):
    answer: str
    intent: str
    data: list[dict] = []
    suggested_actions: list[SuggestedAction] = []
    confirmation_required: bool = False

class ChatHistoryRead(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int;role:str;message:str;response:str;intent:str;created_at:datetime
