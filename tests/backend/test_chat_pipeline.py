import asyncio
import json
from app.services.chat_service import chat_service
from app.services.llm_service import llm_service,ProviderCallError
from app.services.rag_service import rag_service
from app.services.tts_service import tts_service

HEADERS={'X-Visitor-Key':'a'*64}


def mock_dependencies(monkeypatch,stream,chunks=None):
    async def retrieve(*args,**kwargs): return chunks if chunks is not None else [{'title':'测试资料','content':'可靠事实','source':'test','score':1,'chunk_id':'test','revision':0}]
    async def synth(*args,**kwargs): return {'ok':False,'engine':'mock','visemes':[]}
    monkeypatch.setattr(rag_service,'retrieve',retrieve)
    monkeypatch.setattr(tts_service,'synthesize',synth)
    monkeypatch.setattr(llm_service,'stream_chat',stream)


def events(response):
    return [json.loads(line[5:].strip()) for line in response.text.splitlines() if line.startswith('data:') and line[5:].strip()!='[DONE]']


def test_short_untagged_answer_is_not_lost(client,monkeypatch):
    async def stream(*args): yield '短。'
    mock_dependencies(monkeypatch,stream)
    result=events(client.post('/api/chat/stream',headers=HEADERS,json={'message':'测试','tts_enabled':False}))
    assert ''.join(e['text'] for e in result if e['type']=='delta')=='短。'


def test_partial_failure_is_explicit_and_does_not_leak_exception(client,monkeypatch):
    async def stream(*args):
        yield '[emotion:calm]部分答案。'
        raise ProviderCallError('fake','private-detail-must-not-leak',True)
    mock_dependencies(monkeypatch,stream)
    response=client.post('/api/chat/stream',headers=HEADERS,json={'message':'测试','tts_enabled':False})
    result=events(response)
    assert 'private-detail-must-not-leak' not in response.text
    assert result[-1]['type']=='done' and result[-1]['status']=='partial'
    assert any(e['type']=='error' and e['partial'] for e in result)


def test_no_evidence_refuses_without_model_call(client,monkeypatch):
    async def stream(*args):
        raise AssertionError('model must not run without evidence')
        yield ''
    mock_dependencies(monkeypatch,stream,[])
    result=events(client.post('/api/chat/stream',headers=HEADERS,json={'message':'外部未知问题','tts_enabled':False}))
    assert result[-1]['type']=='done' and result[-1]['status']=='refused'


def test_cancel_bounds_and_closes_all_speech_work_and_records_outcome(client,monkeypatch):
    async def run():
        started=asyncio.Event(); active=peak=closed=0
        async def synth(*args):
            nonlocal active,peak,closed
            active+=1; peak=max(peak,active)
            if active==4: started.set()
            try: await asyncio.Event().wait()
            finally: active-=1; closed+=1
        async def stream(*args): yield '[emotion:calm]'+('一句话。'*50)
        mock_dependencies(monkeypatch,stream)
        monkeypatch.setattr(tts_service,'synthesize',synth)
        async def consume():
            async for _ in chat_service.stream_pipeline('取消测试','cancel-owner'): pass
        task=asyncio.create_task(consume())
        await asyncio.wait_for(started.wait(),3)
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass
        assert peak<=4 and active==0 and closed==4
        history=await chat_service.get_history('cancel-owner')
        assert history[-1]['outcome']=='cancelled'
        assert await chat_service.get_history('cancel-owner',model_context=True)==[]
    client.portal.call(run)


def test_partial_outcome_persists_and_feedback_id_is_request_specific(client,monkeypatch):
    async def stream(*args): yield '[emotion:calm]成功。'
    mock_dependencies(monkeypatch,stream)
    done=events(client.post('/api/chat/stream',headers=HEADERS,json={'message':'测试','tts_enabled':False}))[-1]
    assert done['persisted'] and done['feedback_id']
    history=client.get('/api/chat/history',headers=HEADERS).json()['history']
    assert history[-1]['request_id']==done['request_id'] and history[-1]['outcome']=='completed'


def test_split_citations_remain_visible_but_are_not_spoken(client,monkeypatch):
    spoken=[]
    async def stream(*args):
        yield '[emotion:calm]'+('正文'*90)+'[ci'
        yield 'te:test]。'
    mock_dependencies(monkeypatch,stream)
    async def synth(text):
        spoken.append(text)
        return {'ok':False,'engine':'mock'}
    monkeypatch.setattr(tts_service,'synthesize',synth)
    result=client.post('/api/chat/send',headers=HEADERS,json={'message':'测试','tts_enabled':True}).json()
    assert '[cite:test]' in result['answer']
    assert spoken and all('[cite:' not in text and '[ci' not in text for text in spoken)


def test_local_no_overlap_is_an_explicit_refused_terminal(client,monkeypatch):
    async def retrieve(*args,**kwargs):
        return [{'title':'云杉展馆','content':'云杉展馆陈列木雕。','source':'fixture','score':1,'chunk_id':'fixture','revision':0}]
    monkeypatch.setattr(rag_service,'retrieve',retrieve)
    result=client.post('/api/chat/send',headers=HEADERS,json={'message':'火星探测器的燃料是什么？','tts_enabled':False}).json()
    assert result['status']=='refused'
    assert result['provenance']['local_refusal'] is True
    assert '[cite:' not in result['answer']
