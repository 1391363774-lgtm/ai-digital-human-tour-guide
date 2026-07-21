from typing import Any

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    conversation_id: int | None = None
    top_k: int = Field(default=5, ge=1, le=10)
    fast: bool = False


class ChatSourceOut(BaseModel):
    content: str
    score: float
    metadata: dict[str, Any]


class ChatMessageResponse(BaseModel):
    answer: str
    provider: str
    model: str
    conversation_id: int | None = None
    sources: list[ChatSourceOut]
    refused: bool = False
