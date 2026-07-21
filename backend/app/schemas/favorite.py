from datetime import datetime

from pydantic import BaseModel, Field


class FavoriteCreate(BaseModel):
    target_type: str = Field(pattern="^(spot|route|message|qa)$")
    target_id: int


class FavoriteOut(BaseModel):
    id: int
    user_id: int
    target_type: str
    target_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
