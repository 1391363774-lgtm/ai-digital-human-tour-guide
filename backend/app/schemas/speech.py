from pydantic import BaseModel


class AsrResponse(BaseModel):
    text: str
    language: str | None
    duration: float | None
    segments: list[dict]


class TtsRequest(BaseModel):
    text: str
    voice: str | None = None
    rate: float = 1.0
