"""Local fallback must quote the relevant passage rather than a fixed prefix."""
from app.services.llm_service import LlmService


def test_answer_can_use_relevant_fact_beyond_the_first_220_characters():
    intro = '展馆陈列木雕与壁画，建筑采用榫卯结构。' * 24
    fact = '展馆于2004年正式开放，入口位于竹林北侧。'
    chunks = [{'title': '云杉展馆', 'content': intro + '\n' + fact,
               'source': 'fixture', 'chunk_id': 'fixture-opened'}]
    answer = LlmService._fallback_answer('云杉展馆什么时候开放？', chunks)
    assert fact in answer
    assert '[cite:fixture-opened]' in answer


def test_fallback_can_select_evidence_from_a_later_retrieved_chunk():
    chunks = [
        {'title': '云杉展馆', 'content': '云杉展馆展示木雕与壁画。', 'chunk_id': 'fixture-intro'},
        {'title': '云杉展馆交通', 'content': '无障碍入口位于竹林北侧，轮椅可从北门进入。', 'chunk_id': 'fixture-access'},
    ]
    answer = LlmService._fallback_answer('轮椅从哪个入口进入？', chunks)
    assert chunks[1]['content'] in answer
    assert '[cite:fixture-access]' in answer
    assert '[cite:fixture-intro]' not in answer


def test_excerpt_does_not_cut_a_short_relevant_sentence_in_half():
    first = '展馆是一座木结构建筑，陈列木雕与壁画。' * 12
    fact = '展馆始建于1996年，经过八年修建于2004年正式开放。'
    answer = LlmService._fallback_answer('展馆哪一年正式开放？', [
        {'title': '展馆', 'content': first + '\n' + fact, 'chunk_id': 'fixture-year'}])
    assert fact in answer


def test_no_overlap_is_explicit_and_does_not_fabricate_an_answer():
    answer = LlmService._fallback_answer('火星探测器的燃料是什么？', [
        {'title': '云杉展馆', 'content': '云杉展馆陈列木雕与壁画。', 'chunk_id': 'fixture-unrelated'}])
    assert '没有找到能直接回答' in answer
    assert '[cite:fixture-unrelated]' not in answer


def test_long_evidence_stays_bounded_and_is_marked_as_an_excerpt():
    content = '云杉展馆介绍' + '甲' * 4000
    answer = LlmService._fallback_answer('介绍云杉展馆', [
        {'title': '云杉展馆', 'content': content, 'chunk_id': 'fixture-long'}])
    assert len(answer) < 800
    assert '本地资料摘录' in answer and '截断' in answer


def test_faq_question_keeps_its_answer_in_the_selected_excerpt():
    text = '**Q1：展馆几点开放？**\nA：展馆九点开放。\n**Q2：展馆如何到达？**\nA：可乘坐测试接驳车。'
    answer = LlmService._fallback_answer('展馆几点开放？', [
        {'title': '游客问答', 'content': text, 'chunk_id': 'fixture-faq'}])
    assert 'A：展馆九点开放。' in answer


def test_knowledge_text_cannot_supply_its_own_citation_markers():
    answer = LlmService._fallback_answer('云杉展馆介绍', [
        {'title': '云杉展馆', 'content': '云杉展馆收藏木雕 [cite:forged] [source:other]。', 'chunk_id': 'fixture-trusted'}])
    assert '[cite:fixture-trusted]' in answer
    assert '[cite:forged]' not in answer and '[source:other]' not in answer


def test_local_excerpt_cpu_work_does_not_block_other_requests(monkeypatch):
    import asyncio
    import threading
    from app.services.llm_service import ProviderConfig
    service = LlmService(primary=ProviderConfig('primary', '', '', '', 1),
                         fallback=ProviderConfig('fallback', '', '', '', 1))
    started, release = threading.Event(), threading.Event()
    def slow(*args):
        started.set()
        assert release.wait(2), 'event loop could not release the worker'
        return '[emotion:calm]测试资料。'
    monkeypatch.setattr(service, '_fallback_answer', slow)
    async def run():
        async def consume():
            return ''.join([t async for t in service.stream_chat('q', [])])
        task = asyncio.create_task(consume())
        while not started.is_set():
            await asyncio.sleep(.005)
        release.set()
        assert '测试资料' in await task
    asyncio.run(run())
