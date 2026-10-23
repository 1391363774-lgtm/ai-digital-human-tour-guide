"""
游客情感分析 - 轻量词典法(毫秒级,零成本) + 可选LLM精判
用于管理后台"游客感受度报告"的数据来源
"""
from typing import Tuple

# 中文情感词典(景区场景定制)
_POSITIVE = {
    "好", "棒", "赞", "美", "壮观", "震撼", "漂亮", "好看", "喜欢", "满意",
    "感谢", "谢谢", "不错", "推荐", "值得", "精彩", "开心", "舒服", "方便",
    "震撼", "神奇", "宏伟", "庄严", "清净", "好玩", "有趣", "惊喜", "完美",
}
_NEGATIVE = {
    "差", "烂", "坑", "贵", "累", "挤", "排队", "等太久", "失望", "难吃",
    "不好", "垃圾", "骗", "投诉", "态度差", "混乱", "脏", "麻烦", "不方便",
    "迷路", "找不到", "太贵", "不值", "无聊", "扫兴", "糟糕", "气愤",
}
_INTENSIFIER = {"很", "非常", "特别", "太", "真", "好", "十分", "极其"}
_NEGATION = {"不", "没", "没有", "别", "无"}


def analyze_sentiment(text: str) -> Tuple[str, float]:
    """
    返回 (sentiment, score)
    sentiment: positive / neutral / negative
    score: 0~1 置信度
    """
    if not text:
        return "neutral", 0.5
    pos = neg = 0
    chars = list(text)
    for i, ch in enumerate(chars):
        window = text[max(0, i - 2):i]
        intensified = any(w in window for w in _INTENSIFIER)
        negated = any(w in window for w in _NEGATION)
        weight = 2 if intensified else 1
        if ch in _POSITIVE:
            if negated:
                neg += weight
            else:
                pos += weight
        elif ch in _NEGATIVE:
            if negated:
                pos += weight
            else:
                neg += weight
    # 双字负向词补偿
    for w in ["等太久", "态度差", "排队", "失望", "不值", "扫兴"]:
        if w in text:
            neg += 2
    if pos == 0 and neg == 0:
        return "neutral", 0.55
    if pos > neg:
        return "positive", min(0.6 + (pos - neg) * 0.1, 0.95)
    if neg > pos:
        return "negative", min(0.6 + (neg - pos) * 0.1, 0.95)
    return "neutral", 0.5
