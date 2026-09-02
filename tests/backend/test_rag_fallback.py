from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.embedding_service import EmbeddingResult  # noqa: E402
from app.services.rag_service import RagHit, RagService  # noqa: E402


class StubEmbeddingService:
    def embed_query(self, query: str) -> EmbeddingResult:
        return EmbeddingResult(query, [1.0], "test", 1)


class BrokenVectorStore:
    calls = 0

    def search(self, vector, top_k=5):
        self.calls += 1
        raise ValueError("corrupt local index")


def test_vector_store_failure_falls_back_to_lexical_search():
    RagService._cache.clear()
    RagService._vector_disabled_until = 0
    service = object.__new__(RagService)
    service.embedding_service = StubEmbeddingService()
    service.vector_store = BrokenVectorStore()
    service._spot_name_boost = lambda *args, **kwargs: []
    service._fallback_lexical_search = lambda *args, **kwargs: [
        RagHit("灵山大佛通高88米", 1.0, {"retrieval": "lexical_fallback"})
    ]

    hits = service.search("损坏索引回退测试", top_k=3)

    assert len(hits) == 1
    assert hits[0].source["retrieval"] == "lexical_fallback"

    second = service.search("损坏索引回退测试二", top_k=3)
    assert len(second) == 1
    assert service.vector_store.calls == 1
    RagService._vector_disabled_until = 0
