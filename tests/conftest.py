import os
from pathlib import Path
import socket
import sys
import pytest
import asyncio
import importlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
os.environ['GUIDE_NO_ENV_FILE']='1'
os.environ['LLM_API_KEY']=''
os.environ['LLM_FALLBACK_API_KEY']=''
os.environ['DATABASE_URL']='sqlite+aiosqlite://'


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    original=socket.socket.connect
    def connect(sock,address):
        if isinstance(address,tuple) and address[0] not in ('127.0.0.1','localhost','::1'):
            raise AssertionError('offline regression forbids external network')
        return original(sock,address)
    monkeypatch.setattr(socket.socket,'connect',connect)


@pytest.fixture
def client(monkeypatch, tmp_path):
    from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
    from fastapi.testclient import TestClient
    from app.core.config import settings
    dbmod=importlib.import_module('app.core.database')
    chatmod=importlib.import_module('app.services.chat_service')
    engine=create_async_engine('sqlite+aiosqlite:///'+(tmp_path/'test.db').as_posix())
    sessions=async_sessionmaker(engine,expire_on_commit=False)
    monkeypatch.setattr(dbmod,'engine',engine)
    monkeypatch.setattr(dbmod,'async_session',sessions)
    monkeypatch.setattr(chatmod,'async_session',sessions)
    if hasattr(settings,'ADMIN_API_KEY'):
        monkeypatch.setattr(settings,'ADMIN_API_KEY','test-admin')
    from app.main import app
    with TestClient(app) as c:
        yield c
    asyncio.run(engine.dispose())
