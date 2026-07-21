from pydantic import BaseModel, Field


class ScenicSpotBase(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    scenic_area: str = "灵山胜境"
    location: str | None = None
    category: str | None = None
    parameters: str | None = None
    core_function: str | None = None
    cultural_meaning: str | None = None
    description: str | None = None
    highlights: str | None = None
    open_info: str | None = None
    remarks: str | None = None
    recommended_duration_minutes: int | None = None
    latitude: float | None = None
    longitude: float | None = None


class ScenicSpotCreate(ScenicSpotBase):
    pass


class ScenicSpotUpdate(BaseModel):
    name: str | None = None
    scenic_area: str | None = None
    location: str | None = None
    category: str | None = None
    parameters: str | None = None
    core_function: str | None = None
    cultural_meaning: str | None = None
    description: str | None = None
    highlights: str | None = None
    open_info: str | None = None
    remarks: str | None = None
    recommended_duration_minutes: int | None = None
    latitude: float | None = None
    longitude: float | None = None


class ScenicSpotOut(ScenicSpotBase):
    id: int

    model_config = {"from_attributes": True}
