"""生成标准问答评测集。"""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET = PROJECT_ROOT / "data" / "eval" / "qa_testset.json"


SPOTS = [
    ("LS-001", "灵山大照壁", "佛教文化", ["照壁", "灵山", "佛教"]),
    ("LS-002", "五明桥", "佛教文化", ["五明", "桥", "智慧"]),
    ("LS-003", "佛足坛", "佛教文化", ["佛足", "礼佛", "坛"]),
    ("LS-004", "五智门", "佛教文化", ["五智", "入口", "佛教"]),
    ("LS-005", "菩提大道", "佛教文化", ["菩提", "大道", "朝圣"]),
    ("LS-006", "九龙灌浴", "演艺体验", ["九龙", "灌浴", "演艺"]),
    ("LS-007", "降魔成道", "演艺体验", ["降魔", "成道", "表演"]),
    ("LS-008", "灵山梵宫", "佛教文化", ["梵宫", "艺术", "文化"]),
    ("LS-009", "五印坛城", "佛教文化", ["坛城", "五印", "藏传"]),
    ("LS-010", "灵山大佛", "佛教文化", ["大佛", "释迦牟尼", "祈福"]),
    ("NHW-001", "拈花塔", "景观打卡", ["拈花塔", "小镇", "打卡"]),
    ("NHW-002", "香月花街", "休闲体验", ["花街", "商业", "休闲"]),
    ("NHW-003", "拈花湾禅意小镇", "休闲体验", ["禅意", "小镇", "休闲"]),
    ("NHW-004", "微笑广场", "景观打卡", ["微笑", "广场", "景观"]),
    ("NHW-005", "妙音台", "演艺体验", ["妙音台", "演艺", "音乐"]),
    ("NHW-006", "半山衔日", "景观打卡", ["半山", "观景", "日落"]),
]


GENERAL = [
    ("灵山胜境适合什么类型的游客？", ["灵山", "佛教", "文化"]),
    ("如果游客喜欢历史文化，路线应该优先推荐哪些类型的景点？", ["历史文化", "佛教文化", "灵山"]),
    ("如果游客只有三小时，导览系统应该怎样安排路线？", ["三小时", "路线", "重点"]),
    ("景区问答不能回答哪些问题？", ["景区", "无关", "拒答"]),
    ("游客反馈为什么要做情绪分析？", ["反馈", "情绪", "满意度"]),
    ("数据大屏主要展示哪些运营指标？", ["数据大屏", "反馈", "行为"]),
    ("知识库上传后为什么要切分成知识块？", ["知识库", "切分", "检索"]),
    ("没有云端 TTS Key 时系统如何处理语音播报？", ["浏览器", "TTS", "降级"]),
    ("没有大模型 Key 时问答系统如何保证可演示？", ["本地", "降级", "问答"]),
    ("游客行为数据能帮助景区做什么？", ["行为", "热点", "运营"]),
    ("收藏功能对游客路线规划有什么帮助？", ["收藏", "路线", "兴趣"]),
    ("为什么路线推荐要考虑同行人群？", ["同行", "人群", "路线"]),
    ("景点后台可以维护哪些信息？", ["景点", "后台", "维护"]),
    ("历史记录页面对游客有什么价值？", ["历史", "会话", "查看"]),
    ("RAG 检索在景区问答中解决什么问题？", ["RAG", "知识库", "准确"]),
    ("灵山胜境和拈花湾在体验风格上有什么差异？", ["灵山", "拈花湾", "文化"]),
    ("如何识别游客提交的高优先级反馈？", ["负向", "满意度", "优先级"]),
    ("行为数据 CSV 导入需要哪些关键字段？", ["event_type", "session_id", "spot_id"]),
    ("数据大屏中的平均响应延迟代表什么？", ["响应", "延迟", "消息"]),
    ("为什么需要官方结构化景点数据导入？", ["官方", "结构化", "景点"]),
]


def build_dataset() -> list[dict]:
    dataset: list[dict] = []
    for code, name, category, keywords in SPOTS:
        dataset.extend(
            [
                {
                    "id": f"{code}-intro",
                    "question": f"请介绍{name}。",
                    "expected_keywords": [name, *keywords[:2]],
                    "category": "spot_intro",
                },
                {
                    "id": f"{code}-category",
                    "question": f"{name}属于什么游览类型？",
                    "expected_keywords": [name, category],
                    "category": "spot_category",
                },
                {
                    "id": f"{code}-route",
                    "question": f"路线推荐里为什么可以安排{name}？",
                    "expected_keywords": [name, "路线", category],
                    "category": "route_reason",
                },
                {
                    "id": f"{code}-highlight",
                    "question": f"{name}有什么游玩亮点？",
                    "expected_keywords": [name, "亮点", *keywords[:1]],
                    "category": "spot_highlight",
                },
                {
                    "id": f"{code}-qa",
                    "question": f"游客问到{name}时，AI 导游回答应包含哪些核心信息？",
                    "expected_keywords": [name, "导游", *keywords[:1]],
                    "category": "guide_answer",
                },
            ]
        )

    for index, (question, keywords) in enumerate(GENERAL, start=1):
        dataset.append(
            {
                "id": f"general-{index:03d}",
                "question": question,
                "expected_keywords": keywords,
                "category": "general",
            }
        )

    return dataset[:100]


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    dataset = build_dataset()
    TARGET.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"生成评测集：{TARGET}，共 {len(dataset)} 条。")


if __name__ == "__main__":
    main()
