"""Reproduce lexical misses without cloud APIs or lowering the score threshold."""
import pytest

from app.services.rag_service import RagService, _TfidfEngine


def test_punctuation_and_conversational_fillers_are_not_search_evidence():
    tokens = _TfidfEngine._tokenize('嗯，那个到底是什么呀？？？')
    assert not tokens


@pytest.mark.parametrize('query', [
    '那个很高的大佛到底有多高啊？',
    '玄奘和灵山有什么关系？',
    '微笑广场为什么叫这个名字？',
    '我想了解梵宫的建筑风格。',
])
def test_known_scenic_questions_retrieve_existing_evidence(client, query):
    from app.services.rag_service import rag_service
    assert client.portal.call(rag_service.retrieve, query)


@pytest.mark.parametrize('query', [
    '你知道今天股市行情吗？',
    '你能帮我算一道数学题吗？123乘以456等于多少？',
])
def test_unrelated_questions_do_not_match_question_punctuation(client, query):
    from app.services.rag_service import rag_service
    assert client.portal.call(rag_service.retrieve, query) == []


def test_fillers_do_not_displace_evidence_in_an_unrelated_fixture_corpus():
    chunks = [
        {'title': '云杉展馆', 'content': '云杉展馆收藏木雕，采用榫卯结构。', 'source': 'fixture-hall'},
        {'title': '竹影步道', 'content': '竹影步道环绕荷塘，设有无障碍入口。', 'source': 'fixture-path'},
    ]
    records, _, engine = RagService._prepare(chunks, (0, 800, 80))
    snapshot = {'chunks': records, 'tfidf': engine, 'vectors': None, 'state': (0, 800, 80)}
    results = RagService._rank(snapshot, '嗯，那个云杉展馆到底收藏什么呀？', None, 4)
    assert results and results[0]['source'] == 'fixture-hall'
