from app.services.rag_service import rag_service

ADMIN={'X-Admin-Key':'test-admin'}


def search(client,text):
    return client.portal.call(rag_service.retrieve,text)


def create(client):
    return client.post('/api/knowledge/items',headers=ADMIN,json={'category':'test','title':'蓝鲸回归馆','content':'独家资料：橙色暗号，开放八十八分钟。','status':'published'}).json()['id']


def test_published_add_is_immediately_retrievable(client):
    item=create(client)
    assert any(c['source']==f'ADMIN-{item}' for c in search(client,'蓝鲸回归馆'))


def test_modified_and_deleted_chunks_cannot_survive(client):
    item=create(client)
    client.portal.call(rag_service.build)
    assert any(c['source']==f'ADMIN-{item}' for c in search(client,'蓝鲸回归馆'))
    client.put(f'/api/knowledge/items/{item}',headers=ADMIN,json={'content':'独家资料：紫色暗号。'})
    results=[c for c in search(client,'蓝鲸回归馆') if c['source']==f'ADMIN-{item}']
    assert results and all('橙色暗号' not in c['content'] for c in results)
    assert client.delete(f'/api/knowledge/items/{item}',headers=ADMIN).status_code==200
    assert all(c['source']!=f'ADMIN-{item}' for c in search(client,'蓝鲸回归馆'))


def test_embedding_model_changes_vector_cache_identity(monkeypatch):
    from app.core.config import settings
    first=rag_service._source_hash(['same document'])
    monkeypatch.setattr(settings,'EMBEDDING_MODEL','different-embedding-model')
    assert rag_service._source_hash(['same document']) != first


def test_rechunk_publishes_new_generation_and_discards_query_cache(client):
    item=create(client)
    client.put(f'/api/knowledge/items/{item}',headers=ADMIN,json={'content':'蓝鲸回归馆内容。'*100})
    search(client,'蓝鲸回归馆')
    before=rag_service.status['revision']
    rag_service._query_cache[('stale',)]='old'
    response=client.post('/api/knowledge/rechunk',headers=ADMIN,json={'size':100,'overlap':20})
    assert response.status_code==200
    assert rag_service.status['revision']>before
    assert not rag_service._query_cache
    assert all(len(c['content'])<=100 for c in rag_service.chunks)
    assert client.post('/api/knowledge/rechunk',headers=ADMIN,json={'size':100,'overlap':100}).status_code==422


def test_invalid_old_vector_cache_is_removed(client,tmp_path,monkeypatch):
    import numpy as np
    from app.core.config import settings
    path=tmp_path/'vectors.npz'
    np.savez(path,hash=np.frombuffer(b'old-format',dtype=np.uint8),vectors=np.ones((2,3)))
    monkeypatch.setattr(settings,'VECTOR_CACHE',str(path))
    assert client.portal.call(rag_service._load_or_embed,['new document']) is None
    assert not path.exists()


def test_index_cpu_work_does_not_block_event_loop(client,monkeypatch):
    import asyncio,time
    original=rag_service._prepare
    def slow(*args):
        time.sleep(0.15)
        return original(*args)
    monkeypatch.setattr(rag_service,'_prepare',slow)
    async def run():
        ticks=[]
        async def tick():
            start=time.monotonic()
            while time.monotonic()-start<0.2:
                ticks.append(time.monotonic())
                await asyncio.sleep(0.01)
        await asyncio.gather(rag_service.build(),tick())
        assert max(b-a for a,b in zip(ticks,ticks[1:]))<0.1
    client.portal.call(run)


def test_failed_build_never_publishes_half_index(client,monkeypatch):
    import pytest
    snapshot=rag_service._snapshot
    async def fail(_): raise RuntimeError('injected rebuild failure')
    monkeypatch.setattr(rag_service,'_load_or_embed',fail)
    with pytest.raises(RuntimeError): client.portal.call(rag_service.build)
    assert rag_service._snapshot is snapshot
