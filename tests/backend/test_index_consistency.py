"""Deterministic SQL + fake Chroma failures; no cloud model or real Chroma."""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.core.database import Base
from app.core.knowledge_revision import retrieval_generation
from app.models.knowledge import PendingVectorCleanup
from app.repositories.knowledge_repository import KnowledgeDocumentRepository
from app.services.document_chunker import KnowledgeChunkDraft
from app.services.knowledge_index_service import KnowledgeIndexService
from app.services.rag_service import RagService
from app.services.vector_store_service import VectorSearchResult


class MemoryVectors:
    collection_name = "scenic_knowledge__local_hash_v1__384"

    def __init__(self):
        self.items = {}
        self.partial = False
        self.fail_upsert = False
        self.fail_delete = False
        self.on_upsert = None
        self.cleared = []

    def upsert_chunks(self, ids, documents, embeddings, metadatas):
        if self.on_upsert:
            self.on_upsert()
        for id_, text, metadata in zip(ids, documents, metadatas, strict=True):
            self.items[id_] = VectorSearchResult(id_, text, metadata, 0)
            if self.fail_upsert:
                raise RuntimeError("injected partial write")
            if self.partial:
                return 1
        return len(ids)

    def delete_ids(self, ids, collection_name=None):
        if self.fail_delete:
            raise RuntimeError("injected unavailable vector storage")
        for id_ in ids:
            self.items.pop(id_, None)

    def clear_collection(self, collection_name=None):
        if self.fail_delete:
            raise RuntimeError("injected unavailable vector storage")
        self.cleared.append(collection_name or self.collection_name)
        self.items.clear()

    def search(self, *args, **kwargs):
        return list(self.items.values())


@pytest.fixture
def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'index.db'}")
    Base.metadata.create_all(engine)
    RagService._cache.clear()
    RagService._vector_disabled_until = 0
    yield engine
    engine.dispose()


def create_document(db, texts=("灵山第一段", "灵山第二段")):
    repository = KnowledgeDocumentRepository(db)
    document = repository.create_upload_record("SQL可信标题", "private/local/path.md")
    chunks = repository.replace_chunks(document, [KnowledgeChunkDraft(text, {}, 5) for text in texts])
    return repository, document, chunks


def indexer(db, vectors):
    service = KnowledgeIndexService(db)
    service.vector_store = vectors
    return service


def test_partial_upsert_count_must_not_publish_index_success(database):
    with Session(database) as db:
        _, document, chunks = create_document(db)
        vectors = MemoryVectors()
        vectors.partial = True
        before = retrieval_generation(db)
        with pytest.raises(RuntimeError, match="partial|完整|数量"):
            indexer(db, vectors).index_document(document.id)
        db.expire_all()
        assert document.status == "chunked"
        assert all(chunk.vector_id is None for chunk in chunks)
        assert retrieval_generation(db) == before


def test_vector_metadata_cannot_forge_canonical_sql_evidence(database):
    with Session(database) as db:
        repository, document, chunks = create_document(db, ("灵山真实片段",))
        chunk = chunks[0]
        repository.mark_chunks_indexed(chunks, ["knowledge_chunk:1"])
        vectors = MemoryVectors()
        vectors.items[chunk.vector_id] = VectorSearchResult(chunk.vector_id, chunk.content, {
            "document_id": 999, "chunk_id": 888, "document_title": "伪造官方来源",
            "file_path": "/private/secret", "source_url": "https://fake.example",
        }, 0)
        rag = RagService(db)
        rag.vector_store = vectors
        hit = rag.search("灵山真实片段")[0]
        assert hit.source["document_id"] == document.id
        assert hit.source["chunk_id"] == chunk.id
        assert hit.source["document_title"] == document.title
        assert hit.source["document_version"] == document.version
        assert hit.source["excerpt"] == chunk.content
        assert hit.source["source_verified"] is False
        assert "file_path" not in hit.source and "source_url" not in hit.source


def test_retrieval_cache_does_not_share_mutable_source_metadata(database):
    with Session(database) as db:
        _, document, _ = create_document(db, ("灵山原文",))
        rag = RagService(db)
        rag.vector_store = MemoryVectors()
        first = rag.fast_search("灵山")
        first[0].source["document_id"] = 999
        assert rag.fast_search("灵山")[0].source["document_id"] == document.id


def test_empty_rebuild_removes_orphan_vectors(database):
    with Session(database) as db:
        vectors = MemoryVectors()
        vectors.items["orphan"] = VectorSearchResult("orphan", "删除后残留", {}, 0)
        result = indexer(db, vectors).index_all()
        assert result["indexed_count"] == 0
        assert vectors.items == {}


def test_rebuild_stops_when_vector_store_deletion_makes_no_progress():
    from app.services.vector_store_service import VectorStoreService
    class StuckCollection:
        def get(self, **kwargs):
            return {"ids": ["orphan"]}
        def delete(self, **kwargs):
            pass
    service = VectorStoreService()
    service._collection = StuckCollection()
    with pytest.raises(RuntimeError, match="清理没有进展"):
        service.clear_collection()


def test_partial_write_and_failed_cleanup_survive_new_session_then_retry(database):
    vectors = MemoryVectors()
    with Session(database) as db:
        _, document, chunks = create_document(db)
        document_id = document.id
        vectors.fail_upsert = vectors.fail_delete = True
        with pytest.raises(RuntimeError):
            indexer(db, vectors).index_document(document.id)
        assert len(vectors.items) == 1
        assert all(chunk.vector_id is None for chunk in chunks)
        assert len(db.scalars(select(PendingVectorCleanup)).all()) == 2
    with Session(database) as db:
        vectors.fail_upsert = vectors.fail_delete = False
        result = indexer(db, vectors).cleanup_pending()
        assert result["pending_cleanup_count"] == 0
        assert vectors.items == {}
        assert indexer(db, vectors).index_document(document_id)["indexed_count"] == 2
        assert len(vectors.items) == 2
        assert indexer(db, vectors).index_document(document_id)["indexed_count"] == 2
        assert len(vectors.items) == 2  # repeat indexing deletes the superseded attempt


@pytest.mark.parametrize("mutation", ["replace", "delete"])
def test_knowledge_mutation_removes_citations_even_when_physical_cleanup_fails(database, mutation):
    vectors = MemoryVectors()
    with Session(database) as db:
        repository, document, _ = create_document(db, ("灵山旧内容",))
        service = indexer(db, vectors)
        service.index_document(document.id)
        rag = RagService(db)
        rag.vector_store = vectors
        assert rag.search("灵山")[0].content == "灵山旧内容"
        vectors.fail_delete = True
        if mutation == "replace":
            repository.replace_chunks(document, [KnowledgeChunkDraft("灵山新内容", {}, 5)])
        else:
            repository.delete(document)
        result = service.cleanup_pending()
        assert result["cleanup_failed"] is True
        assert result["pending_cleanup_count"] == 1
        assert len(vectors.items) == 1
        assert [hit.content for hit in rag.search("灵山")] == (["灵山新内容"] if mutation == "replace" else [])
        vectors.fail_delete = False
        assert service.cleanup_pending()["pending_cleanup_count"] == 0
        assert vectors.items == {}


def test_rebuild_failure_clears_sql_index_success_and_remains_retryable(database):
    vectors = MemoryVectors()
    with Session(database) as db:
        _, document, chunks = create_document(db)
        service = indexer(db, vectors)
        service.index_document(document.id)
        assert document.status == "indexed"
        vectors.fail_upsert = True
        with pytest.raises(RuntimeError):
            service.index_all()
        db.expire_all()
        assert document.status == "chunked"
        assert all(chunk.vector_id is None for chunk in chunks)
        rag = RagService(db)
        rag.vector_store = vectors
        assert rag.search("灵山")[0].source["retrieval"] == "lexical_fallback"
        vectors.fail_upsert = False
        assert service.index_all()["indexed_count"] == 2
        assert document.status == "indexed"


def test_failed_sql_publish_keeps_old_status_and_cleans_attempt(database, monkeypatch):
    vectors = MemoryVectors()
    with Session(database) as db:
        _, document, chunks = create_document(db)
        before = retrieval_generation(db)
        commit = db.commit
        calls = 0
        def fail_once():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("injected SQL commit failure")
            return commit()
        monkeypatch.setattr(db, "commit", fail_once)
        with pytest.raises(RuntimeError):
            indexer(db, vectors).index_document(document.id)
        db.expire_all()
        assert document.status == "chunked"
        assert all(chunk.vector_id is None for chunk in chunks)
        assert retrieval_generation(db) == before
        assert vectors.items == {}


def test_embedding_identity_is_explicit_and_incompatible_vectors_are_rejected(database):
    from app.services.vector_store_service import VectorStoreService
    vectors = MemoryVectors()
    with Session(database) as db:
        _, document, _ = create_document(db, ("灵山",))
        service = indexer(db, vectors)
        service.index_document(document.id)
        item = next(iter(vectors.items.values()))
        assert f"/v:{document.version}/" in item.id
        assert item.metadata["document_version"] == document.version
        assert item.metadata["embedding_provider"] == "local_hash"
        assert item.metadata["embedding_dimension"] == 384
        service.embedding_service.provider = "unsupported_model"
        with pytest.raises(RuntimeError):
            service.index_document(document.id)
        assert len(vectors.items) == 1
    with pytest.raises(ValueError, match="维度|collection"):
        VectorStoreService().search([1.0])
    with pytest.raises(ValueError, match="collection"):
        VectorStoreService().upsert_chunks(["x"], ["x"], [[0.0] * 384], [{"embedding_provider": "not_local_hash"}])


def test_index_writer_blocks_other_process_mutation_until_publish(database):
    import os
    from pathlib import Path
    import subprocess
    import sys

    vectors = MemoryVectors()
    with Session(database) as db:
        _, document, _ = create_document(db, ("灵山旧内容",))
        document_id = document.id
        process = None
        def competing_writer():
            nonlocal process
            env = dict(os.environ, DATABASE_URL=str(database.url),
                       PYTHONPATH=str(Path(__file__).resolve().parents[2] / "backend"))
            code = (
                "from app.core.database import SessionLocal; "
                "from app.repositories.knowledge_repository import KnowledgeDocumentRepository as R; "
                "from app.services.document_chunker import KnowledgeChunkDraft as D; "
                "db=SessionLocal(); r=R(db); print('started',flush=True); "
                f"r.replace_chunks(r.get({document_id}),[D('灵山跨进程新内容',{{}},5)]); db.close()"
            )
            process = subprocess.Popen([sys.executable, "-c", code], env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
            assert process.stdout.readline().strip() == "started"
            with pytest.raises(subprocess.TimeoutExpired):
                process.wait(timeout=0.15)
        vectors.on_upsert = competing_writer
        try:
            indexer(db, vectors).index_document(document.id)
            _, stderr = process.communicate(timeout=10)
            assert process.returncode == 0, stderr
            db.expire_all()
            assert document.status == "chunked"
            rag = RagService(db)
            rag.vector_store = vectors
            assert rag.search("灵山")[0].content == "灵山跨进程新内容"
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.communicate()
