from test_chat_pipeline import HEADERS
import pytest


def ask(client, **profile):
    return client.post('/api/chat/send', headers=HEADERS,
                       json={'message':'推荐一条游览路线', 'tts_enabled':False, **profile}).json()


def test_history_route_matches_profile_and_has_real_evidence(client):
    result = ask(client, interest='历史文化', time_budget='6小时')
    plan = result['provenance'].get('route_recommendation', {})
    assert result['provenance']['path'] == 'local_route_rules'
    assert plan['status'] == 'matched' and plan['route_id'] == 'ROUTE-1'
    assert plan['duration_minutes'] <= plan['budget_minutes']
    assert '祥符禅寺' in result['answer'] and '实时' in result['answer']
    assert any(s['chunk_id'] in result['answer'] for s in result['sources'] if s['source']=='ROUTE-1')


def test_short_budget_does_not_claim_a_four_hour_route_fits_two_hours(client):
    result = ask(client, companions='带孩子', time_budget='2小时')
    plan = result['provenance'].get('route_recommendation', {})
    assert plan.get('status') == 'no_fit'
    assert plan['route_id'] is None and plan['minimum_minutes'] == 240
    assert '不能保证' in result['answer']


def test_family_route_and_accessibility_boundary(client):
    result = ask(client, companions='老人和孩子', time_budget='4小时')
    plan = result['provenance'].get('route_recommendation', {})
    assert plan.get('route_id') == 'ROUTE-3' and plan['duration_minutes'] == 240
    assert '无障碍' in result['answer'] and '需' in result['answer']


def test_invalid_time_budget_is_explained_instead_of_ignored(client):
    result = ask(client, time_budget='-2小时')
    assert result['provenance'].get('route_recommendation', {}).get('status') == 'invalid_budget'


def test_preferences_are_request_scoped_and_do_not_replace_factual_questions(client):
    first = ask(client, interest='历史文化', time_budget='6小时')
    second = ask(client, companions='孩子', time_budget='4小时')
    assert first['provenance'].get('route_recommendation', {}).get('route_id') == 'ROUTE-1'
    assert second['provenance'].get('route_recommendation', {}).get('route_id') == 'ROUTE-3'
    fact = client.post('/api/chat/send', headers=HEADERS,
        json={'message':'灵山大佛有多高？','tts_enabled':False,'companions':'孩子','time_budget':'4小时'}).json()
    assert fact['provenance']['path']=='local_extractive' and '88' in fact['answer']


def test_time_and_companions_are_sent_to_remote_prompt_without_an_interest():
    from app.services.llm_service import LlmService
    prompt = LlmService._messages('推荐路线', [], [], None, '2小时', '带孩子')[-1]['content']
    assert '2小时' in prompt and '带孩子' in prompt


def test_route_form_does_not_turn_a_factual_model_question_into_a_route_request():
    from app.services.llm_service import LlmService
    prompt=LlmService._messages('灵山大佛有多高？',[],[], '历史文化', '4小时', '孩子')[-1]['content']
    assert '游客画像' not in prompt and '请针对性推荐路线' not in prompt


@pytest.mark.parametrize('text,minutes', [('30分钟',30),('1.5小时',90),('一小时半',90),('两个半小时',150),('六十分钟',60),('十六小时',960),('0小时30分钟',30)])
def test_supported_budget_forms_are_not_silently_misread(text, minutes):
    from app.services.route_service import parse_minutes
    assert parse_minutes(text)==minutes


def test_current_message_overrides_older_form_time(client):
    result = ask(client, message='改为2小时，推荐游览路线', time_budget='6小时')
    plan=result['provenance']['route_recommendation']
    assert plan['budget_minutes']==120 and plan['status']=='no_fit'


def test_night_and_other_area_questions_are_not_given_a_lingshan_day_route(client):
    result = ask(client, message='拈花湾晚上有什么好玩的？', time_budget='6小时')
    assert result['provenance']['path']=='local_extractive'
    assert '夜间' in result['answer']


def test_route_catalog_citations_survive_rechunk_and_copies_are_isolated(client):
    from app.services.rag_service import rag_service
    response=client.post('/api/knowledge/rechunk',headers={'X-Admin-Key':'test-admin'},json={'size':100,'overlap':20})
    assert response.status_code==200
    result=ask(client,time_budget='6小时',interest='历史文化')
    source=next(s for s in result['sources'] if s['source']=='ROUTE-1')
    assert '出口' in source['content'] and source['chunk_id'] in result['answer']
    assert source['retrieval_method']=='route_catalog' and 'score' not in source
    assert all(len(c['content'])<=100 for c in rag_service.chunks)
    first=client.portal.call(lambda: rag_service.retrieve('推荐路线',include_routes=True))
    first[0]['route_data']['name']='mutated'
    again=client.portal.call(lambda: rag_service.retrieve('推荐路线',include_routes=True))
    assert again[0]['route_data']['name']!='mutated'
