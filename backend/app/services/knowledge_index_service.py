from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.repositories.knowledge_repository import KnowledgeDocumentRepository
from app.services.embedding_service import EmbeddingService
from app.services.vector_store_service import VectorStoreService


class KnowledgeIndexService:
    def __init__(self, db: Session) -> None:
        self.repository = KnowledgeDocumentRepository(db)
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStoreService()

    def index_document(self, document_id: int) -> dict[str, int]:
        chunks = self.repository.list_chunks_for_indexing(document_id=document_id)
        if not chunks:
            return {"indexed_count": 0}
        return self._index_chunks(chunks)

    def index_all(self) -> dict[str, int]:
        chunks = self.repository.list_chunks_for_indexing()
        if not chunks:
            return {"indexed_count": 0}
        return self._index_chunks(chunks)

    def _index_chunks(self, chunks) -> dict[str, int]:
        texts = [chunk.content for chunk in chunks]
        embeddings = self.embedding_service.embed_texts(texts)
        vector_ids = [f"knowledge_chunk:{chunk.id}" for chunk in chunks]
        metadatas = [
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "spot_id": chunk.spot_id or "",
                "chunk_index": chunk.chunk_index,
                "token_count": chunk.token_count,
                **load_metadata(chunk.metadata_json),
            }
            for chunk in chunks
        ]
        count = self.vector_store.upsert_chunks(
            ids=vector_ids,
            documents=texts,
            embeddings=[item.vector for item in embeddings],
            metadatas=metadatas,
        )
        self.repository.mark_chunks_indexed(chunks, vector_ids)
        return {"indexed_count": count}


def load_metadata(value: str | None) -> dict:
    if not value:
        return {}
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}
