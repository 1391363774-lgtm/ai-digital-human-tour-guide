from __future__ import annotations

import logging
from collections import defaultdict
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.knowledge_revision import bump_knowledge_revision
from app.models.knowledge import KnowledgeChunk, PendingVectorCleanup
from app.repositories.knowledge_repository import KnowledgeDocumentRepository
from app.services.embedding_service import EmbeddingService
from app.services.vector_store_service import KNOWLEDGE_COLLECTION, VectorStoreService

logger = logging.getLogger(__name__)


class KnowledgeIndexService:
    """One knowledge writer at a time, guarded by a shared SQL write lock.

    Only CPU local_hash + local Chroma are supported here. Do not place remote
    embedding calls inside this transaction. SQL and Chroma cannot commit
    atomically: SQL remains authoritative; failed physical cleanup is retryable.
    """
    def __init__(self, db: Session) -> None:
        self.repository = KnowledgeDocumentRepository(db)
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStoreService()

    def index_document(self, document_id: int) -> dict:
        return self._index(document_id)

    def index_all(self) -> dict:
        return self._index(None, rebuild=True)

    def _index(self, document_id: int | None, rebuild: bool = False) -> dict:
        db = self.repository.db
        vector_ids: list[str] = []
        cleared_ids: list[str] = []
        try:
            self.repository.lock_knowledge_writes()
            chunks = self.repository.list_chunks_for_indexing(document_id)
            if document_id is not None and self.repository.get(document_id) is None:
                raise RuntimeError("知识文档不存在")
            if self.embedding_service.provider != "local_hash" or self.embedding_service.dimension != 384:
                raise RuntimeError("当前索引器只支持local_hash / 384维；模型切换需要独立collection和重建")
            if rebuild:
                cleared_ids = [chunk.vector_id for chunk in chunks if chunk.vector_id]
                # Explicit rebuild collects orphans from interrupted processes
                # and from the pre-namespace legacy knowledge collection.
                self.vector_store.clear_collection()
                self.vector_store.clear_collection(collection_name="scenic_knowledge")
            texts = [chunk.content for chunk in chunks]
            embeddings = self.embedding_service.embed_texts(texts)
            if len(embeddings) != len(chunks) or any(
                item.provider != "local_hash" or item.dimension != 384 or len(item.vector) != 384
                for item in embeddings
            ):
                raise RuntimeError("embedding返回数量或模型维度不一致")
            attempt = uuid4().hex
            vector_ids = [f"{KNOWLEDGE_COLLECTION}/document:{chunk.document_id}/v:{chunk.document.version}/chunk:{chunk.id}/{attempt}"
                          for chunk in chunks]
            metadatas = [{
                "chunk_id": chunk.id, "document_id": chunk.document_id,
                "document_version": chunk.document.version,
                "embedding_provider": "local_hash", "embedding_dimension": 384,
                "embedding_revision": "v1",
            } for chunk in chunks]
            count = self.vector_store.upsert_chunks(ids=vector_ids, documents=texts,
                embeddings=[item.vector for item in embeddings], metadatas=metadatas) if chunks else 0
            if count != len(chunks):
                raise RuntimeError("向量写入数量不完整，未发布索引版本")
            if document_id is not None and not chunks:
                self.repository.get(document_id).status = "indexed"
            self.repository.mark_chunks_indexed(chunks, vector_ids)
        except Exception as exc:
            db.rollback()
            self.repository.lock_knowledge_writes()
            self.repository.queue_vector_cleanup(vector_ids, KNOWLEDGE_COLLECTION)
            if cleared_ids:
                changed = False
                for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.vector_id.in_(cleared_ids))):
                    chunk.vector_id = None
                    chunk.document.status = "chunked"
                    changed = True
                if changed:
                    bump_knowledge_revision(db)
            db.commit()
            self.cleanup_pending()
            logger.warning("knowledge_index_failed error_type=%s retryable=true", type(exc).__name__)
            raise RuntimeError("知识索引未完成，数量或存储异常，可重试；当前SQL知识仍可词法检索") from exc
        return {"indexed_count": count, **self.cleanup_pending()}

    def cleanup_pending(self) -> dict:
        db = self.repository.db
        deleted_count = 0
        failed = False
        try:
            self.repository.lock_knowledge_writes()
            pending = list(db.scalars(select(PendingVectorCleanup)).all())
            active = set(db.scalars(select(KnowledgeChunk.vector_id).where(KnowledgeChunk.vector_id.is_not(None))).all())
            by_collection: dict[str, list[str]] = defaultdict(list)
            for item in pending:
                if item.vector_id not in active:
                    by_collection[item.collection_name].append(item.vector_id)
            for collection, ids in by_collection.items():
                for start in range(0, len(ids), 500):
                    batch = ids[start:start + 500]
                    self.vector_store.delete_ids(batch, collection_name=collection)
                    db.execute(delete(PendingVectorCleanup).where(PendingVectorCleanup.vector_id.in_(batch)))
                    deleted_count += len(batch)
            db.commit()
        except Exception as exc:
            db.rollback()
            failed = True
            deleted_count = 0
            logger.warning("knowledge_cleanup_pending error_type=%s retryable=true", type(exc).__name__)
        pending_count = len(db.scalars(select(PendingVectorCleanup.vector_id)).all())
        return {"deleted_vector_count": deleted_count, "pending_cleanup_count": pending_count,
                "cleanup_failed": failed}
