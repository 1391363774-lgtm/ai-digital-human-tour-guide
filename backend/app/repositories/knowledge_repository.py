from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.scenic import ScenicSpot
from app.services.document_chunker import KnowledgeChunkDraft


class KnowledgeDocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_upload_record(self, title: str, file_path: str, uploaded_by: int | None = None) -> KnowledgeDocument:
        document = KnowledgeDocument(
            title=title,
            source_type="upload",
            file_path=file_path,
            status="uploaded",
            uploaded_by=uploaded_by,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get(self, document_id: int) -> KnowledgeDocument | None:
        return self.db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.id == document_id))

    def list(self, limit: int = 50, offset: int = 0) -> list[KnowledgeDocument]:
        statement = (
            select(KnowledgeDocument)
            .order_by(KnowledgeDocument.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())

    def delete(self, document: KnowledgeDocument) -> None:
        self.db.delete(document)
        self.db.commit()

    def mark_parse_failed(self, document: KnowledgeDocument, message: str) -> KnowledgeDocument:
        document.status = "parse_failed"
        document.error_message = message
        self.db.commit()
        self.db.refresh(document)
        return document

    def replace_chunks(
        self,
        document: KnowledgeDocument,
        drafts: list[KnowledgeChunkDraft],
    ) -> list[KnowledgeChunk]:
        self.db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document.id).delete()

        spots = list(self.db.scalars(select(ScenicSpot)).all())
        chunks: list[KnowledgeChunk] = []
        for index, draft in enumerate(drafts):
            spot_id = infer_spot_id(draft.content, draft.metadata, spots)
            chunk = KnowledgeChunk(
                document_id=document.id,
                spot_id=spot_id,
                chunk_index=index,
                content=draft.content,
                metadata_json=dump_metadata(draft.metadata),
                token_count=draft.token_count,
            )
            self.db.add(chunk)
            chunks.append(chunk)

        document.status = "chunked"
        document.error_message = None
        self.db.commit()
        for chunk in chunks:
            self.db.refresh(chunk)
        return chunks

    def list_chunks_for_indexing(self, document_id: int | None = None) -> list[KnowledgeChunk]:
        statement = select(KnowledgeChunk).order_by(KnowledgeChunk.id.asc())
        if document_id is not None:
            statement = statement.where(KnowledgeChunk.document_id == document_id)
        return list(self.db.scalars(statement).all())

    def mark_chunks_indexed(self, chunks: list[KnowledgeChunk], vector_ids: list[str]) -> None:
        for chunk, vector_id in zip(chunks, vector_ids, strict=False):
            chunk.vector_id = vector_id
        document_ids = {chunk.document_id for chunk in chunks}
        for document_id in document_ids:
            document = self.get(document_id)
            if document is not None:
                document.status = "indexed"
                document.error_message = None
        self.db.commit()

    def lexical_search_chunks(self, query: str, limit: int = 5) -> list[KnowledgeChunk]:
        keywords = [part for part in query.split() if part]
        statement = select(KnowledgeChunk).order_by(KnowledgeChunk.id.asc()).limit(limit)
        if keywords:
            for keyword in keywords[:3]:
                statement = statement.where(KnowledgeChunk.content.contains(keyword))
        else:
            statement = statement.where(KnowledgeChunk.content.contains(query[:20]))
        return list(self.db.scalars(statement).all())


def infer_spot_id(content: str, metadata: dict[str, str], spots: list[ScenicSpot]) -> int | None:
    text = f"{metadata.get('section_title', '')}\n{content}"
    for spot in spots:
        if spot.name and spot.name in text:
            return spot.id
        if spot.code and spot.code in text:
            return spot.id
    return None


def dump_metadata(metadata: dict[str, str]) -> str:
    import json

    return json.dumps(metadata, ensure_ascii=False)
