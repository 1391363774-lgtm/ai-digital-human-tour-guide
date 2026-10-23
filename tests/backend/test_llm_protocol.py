"""Adapted from verified old failover/model protocol contracts to the new service."""
import asyncio
import json
import httpx
import pytest
from app.services.llm_service import LlmService,ProviderConfig,ProviderCallError
from scripts.test_llm_failover import assert_http_error_failover,assert_timeout_failover


def event(text):
    return 'data:'+json.dumps({'choices':[{'delta':{'content':text}}]},ensure_ascii=False)+'\n\n'


def service(primary_wire,secondary_wire=None):
    calls=[]
    async def handler(req):
        calls.append(req.url.host)
        wire=primary_wire if req.url.host=='primary.test' else secondary_wire
        return httpx.Response(200,content=wire.encode(),headers={'Content-Type':'text/event-stream'})
    return LlmService(primary=ProviderConfig('primary','https://primary.test','fake','fake',1),fallback=ProviderConfig('fallback','https://secondary.test','fake','fake',1),client_factory=lambda timeout:httpx.AsyncClient(transport=httpx.MockTransport(handler))),calls


def collect(s):
    async def run(): return [t async for t in s.stream_chat('test',[])]
    return asyncio.run(run())


def test_original_http503_and_timeout_regressions():
    asyncio.run(assert_http_error_failover())
    asyncio.run(assert_timeout_failover())


@pytest.mark.parametrize('wire',['data: [DONE]\n\n',event(''),event(' \n\t')+'data: [DONE]\n\n'])
def test_empty_or_whitespace_uses_fallback(wire):
    s,calls=service(wire,event('备用')+'data: [DONE]\n\n')
    assert collect(s)==['备用']
    assert calls==['primary.test','secondary.test']


@pytest.mark.parametrize('tail',['','data: broken\n\n','data: {"choices":[{"delta":{},"finish_reason":"length"}]}\n\n'])
def test_partial_protocol_failure_is_not_success_and_never_mixes(tail):
    s,calls=service(event('部分答案')+tail,event('另一个答案')+'data: [DONE]\n\n')
    async def run():
        stream=s.stream_chat('test',[])
        assert await anext(stream)=='部分答案'
        with pytest.raises(ProviderCallError): await anext(stream)
    asyncio.run(run())
    assert calls==['primary.test']


def test_completed_primary_never_calls_fallback():
    s,calls=service(event('第一段')+event(' ')+event('第二段')+'data: [DONE]\n\n')
    assert ''.join(collect(s))=='第一段 第二段'
    assert calls==['primary.test']
