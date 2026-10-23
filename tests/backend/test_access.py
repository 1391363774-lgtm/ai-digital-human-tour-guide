import pytest


@pytest.mark.parametrize('method,path,payload',[
    ('post','/api/knowledge/items',{'category':'test','title':'test','content':'test'}),
    ('get','/api/analytics/feedback',None),
    ('post','/api/avatar/activate/1',{}),
])
def test_admin_routes_fail_closed(client,method,path,payload):
    kwargs={'json':payload} if payload is not None else {}
    assert client.request(method,path,**kwargs).status_code==401


def test_admin_configuration_missing_is_unavailable(client,monkeypatch):
    from app.core.config import settings
    if hasattr(settings,'ADMIN_API_KEY'):
        monkeypatch.setattr(settings,'ADMIN_API_KEY','')
    assert client.get('/api/knowledge/items',headers={'X-Admin-Key':'test-admin'}).status_code==503


def test_history_does_not_trust_tourist_id(client):
    assert client.get('/api/chat/history/guest').status_code==401
    assert client.get('/api/chat/history/other',headers={'X-Visitor-Key':'a'*64}).status_code==404


def test_public_status_contains_no_credentials(client):
    response=client.get('/api/status')
    assert response.status_code==200
    assert 'test-admin' not in response.text


def test_visits_ignore_spoofed_tourist_id_and_stay_isolated(client):
    one={'X-Visitor-Key':'a'*64}
    two={'X-Visitor-Key':'b'*64}
    data={'tourist_id':'shared-guest','spot_id':'LS-011','spot_name':'灵山大佛'}
    assert client.post('/api/analytics/checkin',headers=one,json=data).status_code==200
    assert client.get('/api/analytics/my-visits?tourist_id=shared-guest',headers=one).json()['total']==1
    assert client.get('/api/analytics/my-visits?tourist_id=shared-guest',headers=two).json()['total']==0


def test_cannot_rate_another_visitors_feedback(client):
    import hashlib
    async def seed():
        from app.core.database import async_session
        from app.models.models import TouristFeedback
        async with async_session() as db:
            row=TouristFeedback(tourist_id=hashlib.sha256(('a'*64).encode()).hexdigest(),question='test',answer='test')
            db.add(row); await db.commit(); return row.id
    fid=client.portal.call(seed)
    assert client.post('/api/analytics/rate',headers={'X-Visitor-Key':'b'*64},json={'feedback_id':fid,'satisfaction':5}).status_code==404
    assert client.post('/api/analytics/rate',headers={'X-Visitor-Key':'a'*64},json={'feedback_id':fid,'satisfaction':5}).json()=={'ok':True}


def test_audio_requires_unexpired_unguessable_grant(client,tmp_path,monkeypatch):
    from app.services.tts_service import tts_service
    monkeypatch.setattr(tts_service,'cache_dir',tmp_path)
    key='a'*32
    (tmp_path/(key+'.mp3')).write_bytes(b'not-a-real-recording')
    meta=tts_service.grant_audio({'audio_url':'/api/tts/audio/'+key})
    assert client.get('/api/tts/audio/'+key).status_code==404
    assert client.get(meta['audio_url']).status_code==200
    token=meta['audio_url'].split('access=')[1]
    tts_service._grants[token]=(key,0)
    assert client.get(meta['audio_url']).status_code==404


def test_model_generated_advisory_priority_cannot_become_html_class(client,monkeypatch):
    import json
    from app.services.llm_service import llm_service
    async def fake(*args,**kwargs):
        return json.dumps([{'priority':'invalid-class-value','content':'公开测试建议'}])
    monkeypatch.setattr(llm_service,'chat_once',fake)
    result=client.post('/api/analytics/suggestions',headers={'X-Admin-Key':'test-admin'}).json()
    assert result['suggestions'][0]=={'priority':'medium','content':'公开测试建议'}
