from pathlib import Path
import asyncio

from fastapi import FastAPI
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.api.routes import knowledge, rag
from app.core.database import Base, get_db
from app.core.access import require_admin
from app.services.rag_service import RagService
from app.services.vector_store_service import VectorStoreService


def test_upload_rechunk_reindex_delete_http_paths_are_fresh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    RagService._cache.clear()
    RagService._vector_disabled_until = 0
    monkeypatch.setattr(VectorStoreService, "search", lambda *args, **kwargs: [])
    monkeypatch.setattr(VectorStoreService, "upsert_chunks", lambda *args, **kwargs: len(kwargs["ids"]))
    monkeypatch.setattr(VectorStoreService, "delete_ids", lambda *args, **kwargs: None)
    monkeypatch.setattr(VectorStoreService, "clear_collection", lambda *args, **kwargs: None)
    app = FastAPI()
    app.include_router(knowledge.router)
    app.include_router(rag.router)

    def db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = db
    app.dependency_overrides[require_admin] = lambda: None
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            async def search():
                response = await client.post("/api/rag/search", json={"query": "灵山", "top_k": 5})
                assert response.status_code == 200, response.text
                return [hit["content"] for hit in response.json()["data"]["hits"]]

            assert await search() == []
            uploaded = await client.post("/api/admin/knowledge/upload", files={"file": ("guide.md", "# Guide\n\n灵山旧知识内容足够长以满足文档解析和切块要求。".encode(), "text/markdown")})
            assert uploaded.status_code == 200, uploaded.text
            document = uploaded.json()["data"]
            path = f"/api/admin/knowledge/{document['id']}"
            assert (await client.post(path + "/chunks")).status_code == 200
            assert "旧知识" in "".join(await search())
            Path(document["file_path"]).write_text("# Guide\n\n灵山新知识内容已更新，必须立即反映到新的检索结果中。", encoding="utf-8")
            assert (await client.post(path + "/chunks")).status_code == 200
            assert "新知识" in "".join(await search())
            assert (await client.post(path + "/index")).status_code == 200
            assert "新知识" in "".join(await search())
            assert (await client.delete(path)).status_code == 200
            assert await search() == []
    try:
        asyncio.run(run())
    finally:
        engine.dispose()
