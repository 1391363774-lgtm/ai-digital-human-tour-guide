from pydantic import BaseModel, Field, field_validator


class AsrResponse(BaseModel):
    text: str
    language: str | None
    duration: float | None
    segments: list[dict]


class TtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    voice: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9-]+$")
    rate: float = Field(default=1.0, ge=0.5, le=1.5, allow_inf_nan=False)
    request_id: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")
    segment_id: str | None = Field(default=None, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")

    @field_validator("text")
    @classmethod
    def nonblank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("TTS 文本不能为空")
        return value


class TtsSegmentRequest(TtsRequest):
    pass
