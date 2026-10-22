"""Real localhost HTTP and fresh migrations; simulated adapters, no paid services."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from io import BytesIO
import wave

import httpx


def test_clean_demo_http_stream_fallback_audio_and_isolation(tmp_path):
    root = Path(__file__).resolve().parents[2]
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    admin = secrets.token_hex(32)
    env = {**os.environ, 'ADMIN_API_KEY': admin, 'PYTHONUTF8': '1'}
    log = tmp_path / 'server.log'
    with log.open('w', encoding='utf-8') as output:
        process = subprocess.Popen([sys.executable, str(root / 'scripts/run_demo.py'), '--port', str(port),
                                    '--state-dir', str(tmp_path / 'state')], cwd=root, env=env,
                                   stdout=output, stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=10,
                              headers={'X-Visitor-Key': secrets.token_hex(32)}) as client:
                deadline = time.monotonic() + 25
                while True:
                    try:
                        health = client.get('/health')
                        if health.status_code == 200: break
                    except httpx.ConnectError: pass
                    assert process.poll() is None, log.read_text(encoding='utf-8')
                    assert time.monotonic() < deadline, 'demo startup timed out'
                    time.sleep(0.05)
                assert health.json()['data']['demo_mode'] is True
                assert client.get('/api/admin/knowledge').status_code == 401
                question = {'message': '介绍灵山大佛', 'fast': False}
                reply = client.post('/api/chat/messages', json=question)
                assert reply.status_code == 200, reply.text
                data = reply.json()['data']
                assert not data['refused'] and data['sources'] and data['provider'] == 'simulated_model'
                source = data['sources'][0]['metadata']
                assert source['chunk_id'] and source['document_id'] and source['excerpt']
                assert 'file_path' not in source and client.get(source['evidence_url']).status_code == 200
                missing = client.post('/api/chat/messages', json={'message': '遥远火星隐秘景点在哪里'})
                assert missing.json()['data']['refused'] is True
                rejected = client.post('/api/demo/fault', json={'fault': 'empty'})
                assert rejected.status_code == 401
                client.post('/api/demo/fault', json={'fault': 'empty'}, headers={'X-Admin-Key': admin}).raise_for_status()
                stream = client.post('/api/chat/stream', json=question)
                events = [json.loads(line[5:]) for line in stream.text.splitlines() if line.startswith('data:')]
                assert events[-1]['type'] == 'done' and events[-1]['status'] == 'completed'
                assert events[-1]['provider'] == 'local_fallback'
                assert events[-1]['fallback_from'] == ['simulated_model']
                assert len({event['request_id'] for event in events}) == 1
                audio = client.post('/api/speech/tts', json={'text': '静音测试。', 'request_id': 'test', 'segment_id': '0'})
                assert audio.status_code == 200 and audio.headers['content-type'].startswith('audio/wav')
                with wave.open(BytesIO(audio.content)) as wav:
                    assert wav.getframerate() == 16000 and wav.getnchannels() == 1
                    pcm = wav.readframes(wav.getnframes())
                assert set(pcm[:3200]) == {0} and any(pcm[8000:16000])
                assert client.post('/api/speech/asr', files={'file': ('test.wav', audio.content, 'audio/wav')}).status_code == 503
                assert client.post('/api/chat/messages', json={**question, 'conversation_id': data['conversation_id']},
                                   headers={'X-Visitor-Key': secrets.token_hex(32)}).status_code == 404
        finally:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
