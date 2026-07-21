from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    conversation_id: int | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    sentiment: str | None = Field(default=None, max_length=32)
    content: str | None = Field(default=None, max_length=1000)


class FeedbackOut(BaseModel):
    id: int
    user_id: int | None
    conversation_id: int | None
    rating: int | None
    sentiment: str | None
    content: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackAnalysisRequest(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    content: str | None = Field(default=None, max_length=1000)


class FeedbackAnalysisOut(BaseModel):
    sentiment: str
    satisfaction_score: float
    priority: str
    reason: str


class FeedbackAttentionItem(BaseModel):
    id: int
    rating: int | None
    sentiment: str
    satisfaction_score: float
    priority: str
    content: str | None
    created_at: datetime


class FeedbackStatsOut(BaseModel):
    total: int
    average_rating: float
    average_satisfaction: float
    sentiment_counts: dict[str, int]
    priority_counts: dict[str, int]
    latest_at: datetime | None
    attention_items: list[FeedbackAttentionItem]
