"""Real loopback sockets, incremental progress, health responsiveness and disconnect cleanup."""
import asyncio
import functools
import json
import socket
import threading
import time
import httpx
import uvicorn
from app.services.llm_service import llm_service


def test_real_http_progress_health_and_disconnect(client,monkeypatch):
    closed=threading.Event()
    async def stream(*args):
        try:
            yield '[emotion:calm]'
            for i in range(100):
                await asyncio.sleep(0.03)
                yield f'片段{i}'
        finally: closed.set()
    monkeypatch.setattr(llm_service,'stream_chat',stream)
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(128)
    port=listener.getsockname()[1]
    from app.main import app
    server=uvicorn.Server(uvicorn.Config(app,lifespan='off',access_log=False,log_level='error'))
    future=client.portal.start_task_soon(functools.partial(server.serve,sockets=[listener]))
    base=f'http://127.0.0.1:{port}'
    try:
        deadline=time.monotonic()+3
        while not server.started and time.monotonic()<deadline: time.sleep(0.01)
        assert server.started
        headers={'X-Visitor-Key':'c'*64}
        with httpx.Client(timeout=3) as http:
            with http.stream('POST',base+'/api/chat/stream',headers=headers,json={'message':'灵山大佛有多高','tts_enabled':False}) as response:
                assert response.status_code==200
                arrivals=[]
                for line in response.iter_lines():
                    if not line.startswith('data:'): continue
                    event=json.loads(line[5:])
                    if event['type']=='delta':
                        arrivals.append(time.monotonic())
                        if len(arrivals)==2: break
                assert arrivals[1]-arrivals[0]>=0.015
                started=time.monotonic()
                assert http.get(base+'/health').status_code==200
                assert time.monotonic()-started<0.5
            assert closed.wait(3), 'disconnect must close model generator'
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                history=http.get(base+'/api/chat/history',headers=headers).json()['history']
                if history and history[-1]['outcome']=='cancelled': break
                time.sleep(0.02)
            assert history[-1]['outcome']=='cancelled'
    finally:
        server.should_exit=True
        future.result(timeout=5)
        listener.close()
