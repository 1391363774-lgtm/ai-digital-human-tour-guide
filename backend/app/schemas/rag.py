from typing import Any

from pydantic import BaseModel, Field


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class RagSearchHitOut(BaseModel):
    content: str
    score: float
    source: dict[str, Any]


class RagSearchResponse(BaseModel):
    query: str
    hits: list[RagSearchHitOut]
    context: str
