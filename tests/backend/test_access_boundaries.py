import asyncio

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.api.routes import chat, favorite, history, knowledge
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.repositories.conversation_repository import ConversationRepository


@pytest.mark.parametrize('scope', ['admin', 'visitor'])
def test_admin_and_visitor_boundaries(tmp_path, monkeypatch, scope):
    monkeypatch.setenv('ADMIN_API_KEY', 'fixture-admin-key-not-a-secret')
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{tmp_path / 'access.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        # Legacy data is deliberately not claimed by the first new browser.
        ConversationRepository(session).get_or_create(None, 'legacy-private')
    app = FastAPI()
    for router in (chat.router, history.router, knowledge.router, favorite.router):
        app.include_router(router)
    def db():
        with Session(engine) as session: yield session
    app.dependency_overrides[get_db] = db
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            if scope == 'admin':
                assert (await client.get('/api/admin/knowledge')).status_code == 401
                assert (await client.get('/api/admin/knowledge', headers={'X-Admin-Key': 'wrong'})).status_code == 401
                assert (await client.get('/api/admin/knowledge', headers={'X-Admin-Key': 'fixture-admin-key-not-a-secret'})).status_code == 200
                return
            a, b = {'X-Visitor-Key': 'a' * 32}, {'X-Visitor-Key': 'b' * 32}
            created = await client.post('/api/chat/messages', headers=a, json={'message': '门票多少钱'})
            assert created.status_code == 200, created.text
            cid = created.json()['data']['conversation_id']
            assert (await client.get('/api/history', headers=b)).json()['data'] == []
            assert (await client.get(f'/api/history/{cid}', headers=b)).status_code == 404
            assert (await client.post('/api/chat/messages', headers=b, json={'message': '门票', 'conversation_id': cid})).status_code == 404
            assert len((await client.get('/api/history', headers=a)).json()['data']) == 1
            assert (await client.get('/api/history')).status_code == 401
            fav = await client.post('/api/favorites', headers=a, json={'target_type': 'spot', 'target_id': 1})
            assert fav.status_code == 200, fav.text
            assert (await client.get('/api/favorites', headers=b)).json()['data'] == []
            assert (await client.delete(f"/api/favorites/{fav.json()['data']['id']}", headers=b)).status_code == 404
    try: asyncio.run(run())
    finally:
        engine.dispose()
        get_settings.cache_clear()


def test_unconfigured_admin_is_closed(monkeypatch):
    from app.core.access import require_admin
    from fastapi import HTTPException
    monkeypatch.setenv('ADMIN_API_KEY', '')
    get_settings.cache_clear()
    try:
        with pytest.raises(HTTPException) as exc:
            require_admin('anything')
        assert exc.value.status_code == 503
    finally:
        get_settings.cache_clear()
