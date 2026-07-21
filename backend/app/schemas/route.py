from pydantic import BaseModel, Field


class RouteRecommendRequest(BaseModel):
    interest: str = Field(default="历史文化", max_length=100)
    duration_hours: int = Field(default=3, ge=1, le=10)
    group_type: str = Field(default="普通游客", max_length=50)


class RouteSpotOut(BaseModel):
    spot_id: int
    name: str
    category: str | None
    stay_minutes: int
    explanation: str
    highlights: str | None


class RouteRecommendResponse(BaseModel):
    recommendation_id: int | None
    interest: str
    duration_hours: int
    group_type: str
    reason: str
    spots: list[RouteSpotOut]
