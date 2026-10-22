from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.core.knowledge_revision import bump_knowledge_revision
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument, KnowledgeRevision, PendingVectorCleanup
from app.models.scenic import ScenicSpot
from app.services.document_chunker import KnowledgeChunkDraft


class KnowledgeDocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def lock_knowledge_writes(self) -> None:
        # PostgreSQL: row lock; SQLite: write lock. All knowledge mutation and
        # indexing paths take this lock first, including across API processes.
        result = self.db.execute(update(KnowledgeRevision).where(KnowledgeRevision.id == 1)
                                 .values(revision=KnowledgeRevision.revision))
        if result.rowcount != 1:
            raise RuntimeError("knowledge_revision 未初始化，请运行 alembic upgrade head")

    def queue_vector_cleanup(self, vector_ids: list[str], collection_name: str | None = None) -> None:
        for vector_id in set(vector_ids):
            if not vector_id:
                continue
            collection = collection_name or (
                vector_id.split("/", 1)[0] if vector_id.startswith("scenic_knowledge__") else "scenic_knowledge"
            )
            if self.db.get(PendingVectorCleanup, vector_id) is None:
                self.db.add(PendingVectorCleanup(vector_id=vector_id, collection_name=collection))

    def create_upload_record(self, title: str, file_path: str, uploaded_by: int | None = None) -> KnowledgeDocument:
        self.lock_knowledge_writes()
        document = KnowledgeDocument(
            title=title,
            source_type="upload",
            file_path=file_path,
            status="uploaded",
            uploaded_by=uploaded_by,
        )
        self.db.add(document)
        bump_knowledge_revision(self.db)
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
        self.lock_knowledge_writes()
        self.queue_vector_cleanup([chunk.vector_id for chunk in self.list_chunks_for_indexing(document.id)
                                   if chunk.vector_id])
        self.db.delete(document)
        bump_knowledge_revision(self.db)
        self.db.commit()

    def mark_parse_failed(self, document: KnowledgeDocument, message: str) -> KnowledgeDocument:
        self.lock_knowledge_writes()
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
        self.lock_knowledge_writes()
        self.db.refresh(document)
        self.queue_vector_cleanup([chunk.vector_id for chunk in self.list_chunks_for_indexing(document.id)
                                   if chunk.vector_id])
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
        document.version += 1
        document.error_message = None
        bump_knowledge_revision(self.db)
        self.db.commit()
        for chunk in chunks:
            self.db.refresh(chunk)
        return chunks

    def list_chunks_for_indexing(self, document_id: int | None = None) -> list[KnowledgeChunk]:
        statement = (select(KnowledgeChunk).options(joinedload(KnowledgeChunk.document))
                     .execution_options(populate_existing=True).order_by(KnowledgeChunk.id.asc()))
        if document_id is not None:
            statement = statement.where(KnowledgeChunk.document_id == document_id)
        return list(self.db.scalars(statement).all())

    def mark_chunks_indexed(self, chunks: list[KnowledgeChunk], vector_ids: list[str]) -> None:
        if len(chunks) != len(vector_ids):
            raise RuntimeError("索引返回数量不完整，未发布索引版本")
        self.lock_knowledge_writes()
        self.queue_vector_cleanup([chunk.vector_id for chunk in chunks
                                   if chunk.vector_id and chunk.vector_id not in vector_ids])
        for chunk, vector_id in zip(chunks, vector_ids, strict=True):
            chunk.vector_id = vector_id
        document_ids = {chunk.document_id for chunk in chunks}
        for document_id in document_ids:
            document = self.get(document_id)
            if document is not None:
                document.status = "indexed"
                document.error_message = None
        bump_knowledge_revision(self.db)
        self.db.commit()

    def lexical_search_chunks(self, query: str, limit: int = 5) -> list[KnowledgeChunk]:
        keywords = [part for part in query.split() if part]
        statement = (select(KnowledgeChunk).options(joinedload(KnowledgeChunk.document))
                     .execution_options(populate_existing=True).order_by(KnowledgeChunk.id.asc()).limit(limit))
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
