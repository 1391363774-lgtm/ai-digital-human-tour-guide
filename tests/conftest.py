import os
from pathlib import Path
import socket
import sys
import pytest

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
