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


class VectorStoreService:
    def __init__(self, collection_name: str = "scenic_knowledge") -> None:
        self.collection_name = collection_name
        self.settings = get_settings()
        self._collection = None

    def get_collection(self):
        if self._collection is not None:
            return self._collection

        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("缺少 chromadb 依赖，请先安装后端依赖") from exc

        persist_dir = Path(self.settings.chroma_persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = client.get_or_create_collection(name=self.collection_name)
        return self._collection

    def upsert_chunks(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> int:
        if not ids:
            return 0
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
