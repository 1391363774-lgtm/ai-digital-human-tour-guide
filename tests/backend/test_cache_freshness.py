from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.core.database import Base
from app.repositories.knowledge_repository import KnowledgeDocumentRepository
from app.services.document_chunker import KnowledgeChunkDraft
from app.services.rag_service import RagService
from app.services.knowledge_index_service import KnowledgeIndexService
from app.services.vector_store_service import VectorSearchResult


class Vectors:
    def __init__(self):
        self.hits = []

    def search(self, *args, **kwargs):
        return self.hits

    def upsert_chunks(self, ids, documents, embeddings, metadatas):
        self.hits = [VectorSearchResult(id_, content, metadata, 0)
                     for id_, content, metadata in zip(ids, documents, metadatas)]
        return len(ids)


@pytest.fixture
def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'knowledge.db'}")
    Base.metadata.create_all(engine)
    RagService._cache.clear()
    RagService._vector_disabled_until = 0
    yield engine
    engine.dispose()


def replace(repository, document, content):
    return repository.replace_chunks(document, [KnowledgeChunkDraft(content, {}, 5)])


def service(db, vectors=None):
    result = RagService(db)
    result.vector_store = vectors or Vectors()
    return result


@pytest.mark.parametrize("method", ["search", "fast_search"])
@pytest.mark.parametrize("mutation", ["add", "modify", "delete"])
def test_cached_answer_changes_immediately_after_commit(database, method, mutation):
    with Session(database) as reader, Session(database) as writer:
        repository = KnowledgeDocumentRepository(writer)
        document = repository.create_upload_record("test", "unused.md")
        if mutation != "add":
            replace(repository, document, "灵山旧内容")
        search = getattr(service(reader), method)
        old = search("灵山")
        assert bool(old) == (mutation != "add")
        if mutation == "delete":
            repository.delete(document)
        else:
            replace(repository, document, "灵山新内容")
        current = search("灵山")
        assert [hit.content for hit in current] == ([] if mutation == "delete" else ["灵山新内容"])


@pytest.mark.parametrize("mutation", ["modify", "delete"])
def test_stale_vector_payload_cannot_resurrect_old_knowledge(database, mutation):
    with Session(database) as db:
        repository = KnowledgeDocumentRepository(db)
        document = repository.create_upload_record("test", "unused.md")
        chunk = replace(repository, document, "灵山旧内容")[0]
        repository.mark_chunks_indexed([chunk], [f"knowledge_chunk:{chunk.id}"])
        vectors = Vectors()
        vectors.hits = [VectorSearchResult(chunk.vector_id, chunk.content, {"chunk_id": chunk.id}, 0)]
        if mutation == "delete":
            repository.delete(document)
        else:
            replace(repository, document, "灵山新内容")
        current = service(db, vectors).search("灵山")
        assert [hit.content for hit in current] == ([] if mutation == "delete" else ["灵山新内容"])


def test_inflight_old_search_cannot_poison_new_generation(database):
    entered = threading.Event()
    release = threading.Event()
    with Session(database) as db:
        repository = KnowledgeDocumentRepository(db)
        document = repository.create_upload_record("test", "unused.md")
        document_id = document.id
        replace(repository, document, "灵山旧内容")

    def slow_search():
        with Session(database) as db:
            rag = service(db)
            original = rag._fallback_lexical_search

            def pause(*args, **kwargs):
                old = original(*args, **kwargs)
                entered.set()
                assert release.wait(5)
                return old

            rag._fallback_lexical_search = pause
            return rag.search("灵山")

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(slow_search)
        try:
            assert entered.wait(5)
            with Session(database) as db:
                repository = KnowledgeDocumentRepository(db)
                replace(repository, repository.get(document_id), "灵山新内容")
        finally:
            release.set()
        future.result(timeout=5)
    with Session(database) as db:
        assert service(db).search("灵山")[0].content == "灵山新内容"


@pytest.mark.parametrize("mode", ["index_document", "index_all", "empty_rebuild"])
def test_index_completion_invalidates_cached_miss(database, mode):
    from app.core.knowledge_revision import retrieval_generation
    with Session(database) as db:
        repository = KnowledgeDocumentRepository(db)
        document = repository.create_upload_record("test", "unused.md")
        if mode != "empty_rebuild":
            replace(repository, document, "灵山已索引")
        vectors = Vectors()
        rag = service(db, vectors)
        rag._fallback_lexical_search = lambda *args, **kwargs: []
        assert rag.search("灵山") == []
        before = retrieval_generation(db)
        indexer = KnowledgeIndexService(db)
        indexer.vector_store = vectors
        if mode == "index_document":
            indexer.index_document(document.id)
        else:
            indexer.index_all()
        assert retrieval_generation(db)[1] == before[1] + 1
        hits = rag.search("灵山")
        assert [hit.content for hit in hits] == ([] if mode == "empty_rebuild" else ["灵山已索引"])


def test_another_process_commit_invalidates_this_process_cache(database):
    import os
    from pathlib import Path
    import subprocess
    import sys
    with Session(database) as db:
        repository = KnowledgeDocumentRepository(db)
        document = repository.create_upload_record("test", "unused.md")
        replace(repository, document, "灵山旧内容")
        assert service(db).search("灵山")[0].content == "灵山旧内容"
        env = dict(os.environ, DATABASE_URL=str(database.url),
                   PYTHONPATH=str(Path(__file__).resolve().parents[2] / "backend"))
        code = (
            "from app.core.database import SessionLocal; "
            "from app.repositories.knowledge_repository import KnowledgeDocumentRepository as R; "
            "from app.services.document_chunker import KnowledgeChunkDraft as D; "
            "db=SessionLocal(); r=R(db); "
            f"r.replace_chunks(r.get({document.id}),[D('灵山跨进程新内容',{{}},5)]); db.close()"
        )
        result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, timeout=10)
        assert result.returncode == 0, result.stderr
        assert service(db).search("灵山")[0].content == "灵山跨进程新内容"


def test_failed_transaction_does_not_publish_new_revision(database, monkeypatch):
    from app.core.knowledge_revision import retrieval_generation
    with Session(database) as db:
        repository = KnowledgeDocumentRepository(db)
        document = repository.create_upload_record("test", "unused.md")
        replace(repository, document, "灵山旧内容")
        before = retrieval_generation(db)

        def fail():
            raise RuntimeError("commit failed")

        monkeypatch.setattr(db, "commit", fail)
        with pytest.raises(RuntimeError, match="commit failed"):
            replace(repository, document, "灵山未提交内容")
        db.rollback()
        assert retrieval_generation(db) == before
        assert service(db).search("灵山")[0].content == "灵山旧内容"
