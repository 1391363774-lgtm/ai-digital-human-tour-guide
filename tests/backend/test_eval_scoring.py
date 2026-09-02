from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.eval_qa_accuracy import contains_keyword, score_answer_keywords
from app.services.chat_service import build_dynamic_info_refusal


def test_numeric_keyword_does_not_match_part_of_another_number():
    assert not contains_keyword("灵山大佛于1997年建成", "9")
    assert contains_keyword("莲花座高9米", "9")


def test_keyword_alias_group_counts_once():
    score, matched = score_answer_keywords(
        "灵山梵宫占地约3万平方米",
        ["30000", "3万", "三万"],
        [["30000", "3万", "三万"]],
    )

    assert score == 1.0
    assert matched == ["3万"]


def test_multiple_fact_groups_still_require_coverage():
    score, _ = score_answer_keywords(
        "灵山大佛通高88米",
        ["88", "青铜", "释迦牟尼"],
    )

    assert score == 1 / 3


def test_dynamic_ticket_and_hotel_questions_are_not_guessed():
    assert "不能" in build_dynamic_info_refusal("灵山门票多少钱？")
    assert "不能" in build_dynamic_info_refusal("附近有什么酒店可以住？")
    assert build_dynamic_info_refusal("请介绍灵山大佛") is None
