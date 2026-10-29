"""Independent fixtures for subject-dominated and conversational query misses."""
from app.services.llm_service import LlmService


def test_painting_height_beats_repeated_building_name():
    fact = '每幅壁画高4.2米，采用矿物颜料绘制。'
    answer = LlmService._fallback_answer('云杉展馆的壁画有多高？', [{
        'title':'云杉展馆', 'chunk_id':'hall', 'score':.8,
        'content':'云杉展馆位于湖边。云杉展馆展示多种艺术品。云杉展馆周围绿树成荫。'+fact}])
    assert fact in answer.split('[cite:')[0]


def test_weight_question_selects_weight_evidence_instead_of_similar_subject():
    fact = '院内悬挂铜钟，重达7.6吨。'
    answer = LlmService._fallback_answer('青竹寺的大钟有多重？', [{
        'title':'青竹寺', 'chunk_id':'bell', 'score':.8,
        'content':'青竹寺是文化重镇。青竹寺经过多次修复。青竹寺入口设有服务台。'+fact}])
    assert fact in answer.split('[cite:')[0]


def test_colloquial_night_question_selects_night_evidence():
    fact = '夜间可以在云杉园观看灯光展示。'
    answer = LlmService._fallback_answer('云杉园晚上有什么好玩的？', [{
        'title':'云杉园', 'chunk_id':'night', 'score':.8,
        'content':'云杉园临近湖泊。云杉园白天可赏花。云杉园入口设有服务台。'+fact}])
    assert fact in answer.split('[cite:')[0]


def test_introduction_keeps_adjacent_description_instead_of_disjoint_fragments():
    first = '介绍:云杉展馆收藏木雕与壁画。'
    second = '馆内设有榫卯结构互动展台。'
    answer = LlmService._fallback_answer('介绍一下云杉展馆', [{
        'title':'云杉展馆', 'chunk_id':'intro', 'score':.8,
        'content':first+second+'云杉展馆入口可以休息。'}])
    assert first+second in answer


def test_measurement_unit_alone_cannot_answer_an_unrelated_weight_question():
    answer = LlmService._fallback_answer('火星探测器重量是多少？', [{
        'title':'青竹寺', 'chunk_id':'unrelated', 'score':.8,
        'content':'院内悬挂铜钟，重达7.6吨。'}])
    assert '没有找到能直接回答' in answer and '[cite:' not in answer
