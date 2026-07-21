from datetime import datetime

from pydantic import BaseModel


class KnowledgeDocumentOut(BaseModel):
    id: int
    title: str
    source_type: str
    file_path: str | None
    status: str
    version: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ParsedSectionOut(BaseModel):
    title: str
    content_preview: str
    metadata: dict[str, str]


class ParsedDocumentOut(BaseModel):
    title: str
    file_type: str
    section_count: int
    char_count: int
    sections: list[ParsedSectionOut]


class KnowledgeChunkOut(BaseModel):
    id: int
    document_id: int
    spot_id: int | None
    chunk_index: int
    content_preview: str
    token_count: int
