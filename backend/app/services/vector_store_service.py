from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings


@dataclass(frozen=True)
class VectorSearchResult:
    id: str
    content: str
    metadata: dict[str, Any]
    distance: float | None


KNOWLEDGE_COLLECTION = "scenic_knowledge__local_hash_v1__384"


class VectorStoreService:
    def __init__(self, collection_name: str = KNOWLEDGE_COLLECTION) -> None:
        self.collection_name = collection_name
        self.settings = get_settings()
        self._collection = None

    def _client(self):
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("缺少 chromadb 依赖，请先安装后端依赖") from exc
        persist_dir = Path(self.settings.chroma_persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=str(persist_dir))

    def get_collection(self):
        if self._collection is not None:
            return self._collection

        client = self._client()
        self._collection = client.get_or_create_collection(name=self.collection_name)
        return self._collection

    def delete_ids(self, ids: list[str], collection_name: str | None = None) -> None:
        if not ids:
            return
        name = collection_name or self.collection_name
        collection = self.get_collection() if name == self.collection_name else self._client().get_or_create_collection(name=name)
        collection.delete(ids=ids)

    def clear_collection(self, collection_name: str | None = None) -> None:
        # Delete IDs instead of dropping a live collection used by other workers.
        name = collection_name or self.collection_name
        collection = self.get_collection() if name == self.collection_name else self._client().get_or_create_collection(name=name)
        previous_ids = None
        while True:
            ids = collection.get(limit=500, include=[]).get("ids", [])
            if not ids:
                return
            if ids == previous_ids:
                raise RuntimeError("向量清理没有进展，停止重建并允许重试")
            collection.delete(ids=ids)
            previous_ids = ids

    def upsert_chunks(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> int:
        if not ids:
            return 0
        if not (len(ids) == len(documents) == len(embeddings) == len(metadatas)):
            raise ValueError("向量写入数量不一致")
        if self.collection_name == KNOWLEDGE_COLLECTION:
            if any(len(vector) != 384 for vector in embeddings) or any(
                item.get("embedding_provider") != "local_hash" or item.get("embedding_dimension") != 384
                for item in metadatas
            ):
                raise ValueError("当前collection仅支持local_hash v1 / 384维，切换模型必须使用新collection并重建")
        safe_metadatas = [sanitize_metadata(metadata) for metadata in metadatas]
        self.get_collection().upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=safe_metadatas,
        )
        return len(ids)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        if self.collection_name == KNOWLEDGE_COLLECTION and len(query_embedding) != 384:
            raise ValueError("查询向量维度与collection不一致")
        result = self.get_collection().query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [
            VectorSearchResult(
                id=ids[index],
                content=documents[index],
                metadata=metadatas[index] or {},
                distance=distances[index] if index < len(distances) else None,
            )
            for index in range(len(ids))
        ]


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    safe: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            safe[key] = value
        else:
            safe[key] = json.dumps(value, ensure_ascii=False)
    return safe
