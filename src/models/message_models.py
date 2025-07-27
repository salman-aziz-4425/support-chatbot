from typing import List
from pydantic import BaseModel
from autogen_core.models import LLMMessage

class UserLogin(BaseModel):
    customer_id: str

class UserTask(BaseModel):
    context: List[LLMMessage]

class AgentResponse(BaseModel):
    reply_to_topic_type: str
    context: List[LLMMessage] 