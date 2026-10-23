"""Loopback-only integration check; refuses real-service mode before sending a question."""
import argparse
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-url',default='http://127.0.0.1:8080')
    args=parser.parse_args()
    base=args.base_url.rstrip('/')
    if urllib.parse.urlparse(base).hostname not in ('127.0.0.1','localhost','::1'):
        raise SystemExit('Only loopback demo servers are allowed.')
    deadline=time.monotonic()+30
    while True:
        try:
            with urllib.request.urlopen(base+'/api/status',timeout=2) as response:
                status=json.load(response)
            break
        except (OSError,ValueError):
            if time.monotonic()>deadline: raise
            time.sleep(0.2)
    if not status.get('demo_mode') or status.get('llm_available'):
        raise SystemExit('Refusing to query a real-service configuration.')
    visitor=secrets.token_hex(32)
    req=urllib.request.Request(base+'/api/chat/stream',data=json.dumps({'message':'灵山大佛有多高？','tts_enabled':True}).encode(),headers={'Content-Type':'application/json','X-Visitor-Key':visitor})
    with urllib.request.urlopen(req,timeout=20) as response:
        wire=response.read(2_000_000).decode()
    events=[json.loads(line[5:].strip()) for line in wire.splitlines() if line.startswith('data:') and line[5:].strip()!='[DONE]']
    done=events[-1]
    assert done['type']=='done' and done['status']=='completed' and done['persisted']
    assert all(e.get('request_id')==done['request_id'] for e in events)
    sources=next(e['sources'] for e in events if e['type']=='meta')
    assert sources and sources[0]['source']
    audio=next(e for e in events if e['type']=='sentence' and not e.get('prelude') and e.get('audio_url'))
    assert audio['engine']=='demo-tone'
    with urllib.request.urlopen(base+audio['audio_url'],timeout=3) as response:
        assert response.read(4)==b'RIFF'
    def history(key):
        with urllib.request.urlopen(urllib.request.Request(base+'/api/chat/history',headers={'X-Visitor-Key':key}),timeout=3) as response:
            return json.load(response)['history']
    assert history(visitor)[-1]['outcome']=='completed'
    assert history(secrets.token_hex(32))==[]
    print(json.dumps({'mode':'demo','rag':status['rag']['engine'],'terminal':done['status'],'sources':len(sources),'audio':'synthetic WAV fetched','visitor_isolation':'passed','external_model_calls':False},ensure_ascii=False))


if __name__=='__main__': main()
