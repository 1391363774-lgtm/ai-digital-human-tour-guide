from datetime import datetime

from pydantic import BaseModel


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    latency_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: int
    title: str | None
    channel: str
    total_latency_ms: int
    started_at: datetime
    message_count: int


class ConversationDetailOut(BaseModel):
    id: int
    title: str | None
    channel: str
    total_latency_ms: int
    started_at: datetime
    messages: list[MessageOut]
