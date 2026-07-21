from __future__ import annotations

import json
import re
import time
from hashlib import sha256
from dataclasses import dataclass
from typing import Any

import sqlalchemy
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.scenic import ScenicSpot
from app.repositories.knowledge_repository import KnowledgeDocumentRepository
from app.services.embedding_service import EmbeddingService
from app.services.vector_store_service import VectorSearchResult, VectorStoreService


@dataclass(frozen=True)
class RagHit:
    content: str
    score: float
    source: dict[str, Any]


class RagService:
    _cache: dict[str, tuple[float, list[RagHit]]] = {}
    _cache_ttl_seconds = 30 * 60

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = KnowledgeDocumentRepository(db)
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStoreService()

    def search(self, query: str, top_k: int = 5) -> list[RagHit]:
        normalized_query = normalize_query(query)
        if not normalized_query:
            return []

        cache_key = make_cache_key(normalized_query, top_k)
        cached = self._cache.get(cache_key)
        now = time.time()
        if cached and now - cached[0] <= self._cache_ttl_seconds:
            return cached[1]

        vector_hits: list[RagHit] = []
        try:
            query_embedding = self.embedding_service.embed_query(normalized_query)
            results = self.vector_store.search(query_embedding.vector, top_k=top_k * 2)
            if results:
                vector_hits = [self._hit_from_vector_result(item) for item in results]
        except RuntimeError:
            pass

        spot_name_hits = self._spot_name_boost(query, vector_hits, normalized_query)

        if not spot_name_hits:
            spot_name_hits = self._fallback_lexical_search(normalized_query, top_k=top_k)

        merged = _merge_and_dedup(vector_hits + spot_name_hits, top_k=top_k)
        self._cache[cache_key] = (now, merged)
        self._prune_cache(now)
        return merged

    def fast_search(self, query: str, top_k: int = 3) -> list[RagHit]:
        normalized_query = normalize_query(query)
        if not normalized_query:
            return []

        cache_key = make_cache_key(f"fast:{normalized_query}", top_k)
        cached = self._cache.get(cache_key)
        now = time.time()
        if cached and now - cached[0] <= self._cache_ttl_seconds:
            return cached[1]

        hits = self._spot_name_boost(query, [], normalized_query)
        hits.extend(self._fallback_lexical_search(normalized_query, top_k=top_k))
        merged = _merge_and_dedup(hits, top_k=top_k)
        self._cache[cache_key] = (now, merged)
        self._prune_cache(now)
        return merged

    def build_context(self, query: str, top_k: int = 5, max_chars: int = 1600) -> str:
        hits = self.search(query, top_k=top_k)
        parts: list[str] = []
        current_length = 0
        for index, hit in enumerate(hits, start=1):
            source_title = hit.source.get("section_title") or hit.source.get("document_title") or "知识片段"
            block = f"[资料{index}] {source_title}\n{hit.content}"
            if current_length + len(block) > max_chars:
                break
            parts.append(block)
            current_length += len(block)
        return "\n\n".join(parts)

    def _spot_name_boost(
        self, query: str, existing_hits: list[RagHit], normalized_query: str
    ) -> list[RagHit]:
        spots = list(self.db.scalars(
            select(ScenicSpot)
        ).all())
        matched_names = [s.name for s in spots if s.name and s.name in query]
        if not matched_names:
            return []

        existing_content_set = {h.content[:60] for h in existing_hits}
        extra_keywords = " ".join(matched_names[:3])
        extra_chunks = self.repository.lexical_search_chunks(extra_keywords, limit=5)
        boosted: list[RagHit] = []
        for chunk in extra_chunks:
            if chunk.content[:60] in existing_content_set:
                continue
            source = load_metadata(chunk.metadata_json)
            source.update({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "spot_id": chunk.spot_id,
                "retrieval": "spot_name_boost",
            })
            boosted.append(RagHit(
                content=chunk.content,
                score=keyword_score(extra_keywords, chunk.content) + 0.2,
                source=source,
            ))
        return boosted

    def _hit_from_vector_result(self, result: VectorSearchResult) -> RagHit:
        distance = result.distance if result.distance is not None else 1.0
        score = max(0.0, 1.0 - float(distance))
        return RagHit(content=result.content, score=score, source=result.metadata)

    def _fallback_lexical_search(self, query: str, top_k: int) -> list[RagHit]:
        chunks = self.repository.lexical_search_chunks(to_keyword_query(query), limit=top_k)
        hits: list[RagHit] = []
        for chunk in chunks:
            source = load_metadata(chunk.metadata_json)
            source.update({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "spot_id": chunk.spot_id,
                "retrieval": "lexical_fallback",
            })
            hits.append(RagHit(content=chunk.content, score=keyword_score(query, chunk.content), source=source))
        return hits

    def _prune_cache(self, now: float) -> None:
        if len(self._cache) <= 256:
            return
        expired = [
            key
            for key, (created_at, _) in self._cache.items()
            if now - created_at > self._cache_ttl_seconds
        ]
        for key in expired:
            self._cache.pop(key, None)
        while len(self._cache) > 256:
            oldest_key = min(self._cache, key=lambda key: self._cache[key][0])
            self._cache.pop(oldest_key, None)


def _merge_and_dedup(hits: list[RagHit], top_k: int) -> list[RagHit]:
    seen: set[str] = set()
    merged: list[RagHit] = []
    for hit in sorted(hits, key=lambda h: h.score, reverse=True):
        key = hit.content[:60]
        if key not in seen:
            seen.add(key)
            merged.append(hit)
            if len(merged) >= top_k:
                break
    return merged


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query or "").strip()


def make_cache_key(query: str, top_k: int) -> str:
    digest = sha256(query.lower().encode("utf-8")).hexdigest()
    return f"{top_k}:{digest}"


def to_keyword_query(query: str) -> str:
    terms = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]+", query)
    return " ".join(terms[:5]) or query


def keyword_score(query: str, content: str) -> float:
    terms = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]+", query.lower()))
    if not terms:
        return 0.1
    hit_count = sum(1 for term in terms if term in content.lower())
    return hit_count / len(terms)


def load_metadata(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}
