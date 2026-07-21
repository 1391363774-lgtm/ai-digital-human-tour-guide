from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from app.models.feedback import Feedback


POSITIVE_KEYWORDS = {
    "满意",
    "喜欢",
    "不错",
    "很好",
    "清楚",
    "方便",
    "有帮助",
    "推荐",
    "流畅",
    "准确",
    "惊喜",
    "舒服",
}
NEGATIVE_KEYWORDS = {
    "不满意",
    "差",
    "不好",
    "不清楚",
    "错误",
    "卡",
    "慢",
    "失望",
    "麻烦",
    "听不懂",
    "不准",
    "崩溃",
}
STRONG_NEGATIVE_KEYWORDS = {
    "垃圾",
    "很垃圾",
    "太垃圾",
    "难听",
    "很难听",
    "难看",
    "不好看",
    "很不好",
    "很不好看",
    "做得不好",
    "做的不好",
    "体验差",
    "太差",
    "非常差",
    "糟糕",
    "很糟糕",
    "恶心",
    "离谱",
    "坑人",
    "不想再来",
}
NEGATION_PREFIXES = ("不", "没", "没有", "无", "非", "难以", "并不", "不是", "不太")


@dataclass(frozen=True)
class FeedbackAnalysisResult:
    sentiment: str
    satisfaction_score: float
    priority: str
    reason: str


class FeedbackAnalysisService:
    """本地可解释反馈分析，避免依赖付费情绪 API。"""

    def analyze(self, content: str | None = None, rating: int | None = None) -> FeedbackAnalysisResult:
        text = (content or "").strip()
        positive_hits = self._count_positive_hits(text)
        negative_hits = self._count_negative_hits(text)
        strong_negative_hits = sum(1 for keyword in STRONG_NEGATIVE_KEYWORDS if keyword in text)

        score = 50.0
        reasons: list[str] = []
        if rating is not None:
            score = rating * 20.0
            reasons.append(f"评分 {rating}/5")
        if positive_hits:
            score += min(positive_hits * 6.0, 18.0)
            reasons.append(f"正向关键词 {positive_hits} 个")
        if negative_hits:
            score -= min(negative_hits * 18.0, 48.0)
            reasons.append(f"负向关键词 {negative_hits} 个")
        if strong_negative_hits:
            score -= min(strong_negative_hits * 22.0, 55.0)
            reasons.append(f"强负向表达 {strong_negative_hits} 个")

        if strong_negative_hits >= 2 or negative_hits >= 3:
            score = min(score, 35.0)
            reasons.append("文本强负面优先于默认高评分")
        elif strong_negative_hits >= 1 and negative_hits >= 1:
            score = min(score, 42.0)
            reasons.append("明显负面文本下调评分")
        elif rating is not None and rating >= 4 and negative_hits > positive_hits:
            score = min(score, 58.0)
            reasons.append("高评分与负面文本冲突，按文本降权")

        score = max(0.0, min(100.0, round(score, 1)))
        if strong_negative_hits >= 1 and negative_hits >= 1:
            sentiment = "negative"
        elif negative_hits >= 2 and negative_hits >= positive_hits:
            sentiment = "negative"
        elif score >= 70:
            sentiment = "positive"
        elif score <= 45:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        if sentiment == "negative" or score < 45:
            priority = "high"
        elif sentiment == "neutral" or score < 70:
            priority = "medium"
        else:
            priority = "low"

        return FeedbackAnalysisResult(
            sentiment=sentiment,
            satisfaction_score=score,
            priority=priority,
            reason="；".join(reasons) if reasons else "未提供评分或明显情绪关键词，按中性处理",
        )

    def _count_positive_hits(self, text: str) -> int:
        hits = 0
        for keyword in POSITIVE_KEYWORDS:
            if keyword not in text:
                continue
            if self._is_negated(text, keyword):
                continue
            hits += 1
        return hits

    def _count_negative_hits(self, text: str) -> int:
        hits = sum(1 for keyword in NEGATIVE_KEYWORDS if keyword in text)
        for keyword in POSITIVE_KEYWORDS:
            if keyword in text and self._is_negated(text, keyword):
                hits += 1
        return hits

    def _is_negated(self, text: str, keyword: str) -> bool:
        start = 0
        while True:
            index = text.find(keyword, start)
            if index < 0:
                return False
            prefix = text[max(0, index - 4):index]
            if any(prefix.endswith(negation) for negation in NEGATION_PREFIXES):
                return True
            start = index + len(keyword)

    def summarize(self, feedback_items: list[Feedback]) -> dict:
        total = len(feedback_items)
        ratings = [item.rating for item in feedback_items if item.rating is not None]
        average_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0

        analyzed = [
            self.analyze(content=item.content, rating=item.rating)
            for item in feedback_items
        ]
        sentiment_counter = Counter(result.sentiment for result in analyzed)
        priority_counter = Counter(result.priority for result in analyzed)
        average_satisfaction = (
            round(sum(result.satisfaction_score for result in analyzed) / len(analyzed), 2)
            if analyzed
            else 0
        )

        latest_at: datetime | None = max((item.created_at for item in feedback_items), default=None)
        attention_items = [
            {
                "id": item.id,
                "rating": item.rating,
                "sentiment": result.sentiment,
                "satisfaction_score": result.satisfaction_score,
                "priority": result.priority,
                "content": item.content,
                "created_at": item.created_at,
            }
            for item, result in zip(feedback_items, analyzed)
            if result.priority == "high"
        ][:10]

        return {
            "total": total,
            "average_rating": average_rating,
            "average_satisfaction": average_satisfaction,
            "sentiment_counts": {
                "positive": sentiment_counter.get("positive", 0),
                "neutral": sentiment_counter.get("neutral", 0),
                "negative": sentiment_counter.get("negative", 0),
            },
            "priority_counts": {
                "high": priority_counter.get("high", 0),
                "medium": priority_counter.get("medium", 0),
                "low": priority_counter.get("low", 0),
            },
            "latest_at": latest_at,
            "attention_items": attention_items,
        }
