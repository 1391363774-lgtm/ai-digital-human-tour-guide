from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, Message
from app.models.favorite import Favorite
from app.models.feedback import Feedback
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.recommendation import Recommendation
from app.models.scenic import ScenicSpot
from app.models.visitor_event import VisitorEvent
from app.services.feedback_analysis_service import FeedbackAnalysisService


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.feedback_analysis = FeedbackAnalysisService()

    def overview(self, start_date: date | None = None, end_date: date | None = None) -> dict:
        start_at, end_at = to_datetime_range(start_date, end_date)
        feedback_items = self._list_feedback(start_at, end_at)
        behavior_events = self._list_events(start_at, end_at)
        user_messages = self._list_user_messages(start_at, end_at)
        analyzed_feedback = [
            self.feedback_analysis.analyze(content=item.content, rating=item.rating)
            for item in feedback_items
        ]

        ratings = [item.rating for item in feedback_items if item.rating is not None]
        latency_values = [
            value
            for value in self.db.scalars(
                select(Message.latency_ms).where(Message.latency_ms > 0)
            ).all()
        ]
        durations = [event.duration_seconds for event in behavior_events if event.duration_seconds is not None]

        total_spots = self._count(ScenicSpot)
        total_chunks = self._count(KnowledgeChunk)
        total_conversations = self._count(Conversation)
        total_messages = self._count(Message)
        total_routes = self._count(Recommendation)
        total_favorites = self._count(Favorite)

        satisfaction_scores = [item.satisfaction_score for item in analyzed_feedback]
        sentiment_counts = Counter(item.sentiment for item in analyzed_feedback)
        event_type_counts = Counter(event.event_type for event in behavior_events)
        top_spot_counts = Counter(str(event.spot_id) for event in behavior_events if event.spot_id is not None)
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        return {
            "metrics": [
                {"label": "景点数量", "value": total_spots, "unit": "个"},
                {"label": "知识块", "value": total_chunks, "unit": "条"},
                {"label": "会话数", "value": total_conversations, "unit": "次"},
                {"label": "消息数", "value": total_messages, "unit": "条"},
                {"label": "路线推荐", "value": total_routes, "unit": "次"},
                {"label": "收藏数", "value": total_favorites, "unit": "次"},
                {"label": "反馈数", "value": len(feedback_items), "unit": "条"},
                {"label": "行为事件", "value": len(behavior_events), "unit": "条"},
            ],
            "event_type_counts": dict(event_type_counts),
            "feedback_sentiment_counts": {
                "positive": sentiment_counts.get("positive", 0),
                "neutral": sentiment_counts.get("neutral", 0),
                "negative": sentiment_counts.get("negative", 0),
            },
            "favorite_type_counts": self._group_count(Favorite.target_type),
            "knowledge_status_counts": self._group_count(KnowledgeDocument.status),
            "top_spot_counts": dict(top_spot_counts.most_common(10)),
            "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0,
            "average_satisfaction": (
                round(sum(satisfaction_scores) / len(satisfaction_scores), 2) if satisfaction_scores else 0
            ),
            "average_latency_ms": round(sum(latency_values) / len(latency_values), 2) if latency_values else 0,
            "average_duration_seconds": round(sum(durations) / len(durations), 2) if durations else 0,
            "today_visitors": self._count_unique_visitors(today, today),
            "week_visitors": self._count_unique_visitors(week_start, today),
            "questions_trend": self._questions_trend(user_messages, days=7),
            "top_questions": [
                {"question": question, "count": count}
                for question, count in Counter(normalize_question(item.content) for item in user_messages).most_common(10)
                if question
            ],
            "daily_satisfaction": self._daily_satisfaction(feedback_items, days=7),
            "word_cloud": [
                {"word": word, "count": count}
                for word, count in extract_keywords([item.content for item in user_messages]).most_common(30)
            ],
        }

    def _count(self, model: type) -> int:
        return int(self.db.scalar(select(func.count()).select_from(model)) or 0)

    def _group_count(self, column) -> dict[str, int]:
        rows = self.db.execute(select(column, func.count()).group_by(column)).all()
        return {str(key or "unknown"): int(count) for key, count in rows}

    def _list_feedback(self, start_at: datetime | None = None, end_at: datetime | None = None) -> list[Feedback]:
        statement = select(Feedback).order_by(Feedback.created_at.desc()).limit(5000)
        if start_at is not None:
            statement = statement.where(Feedback.created_at >= start_at)
        if end_at is not None:
            statement = statement.where(Feedback.created_at <= end_at)
        return list(self.db.scalars(statement).all())

    def _list_events(self, start_at: datetime | None = None, end_at: datetime | None = None) -> list[VisitorEvent]:
        statement = select(VisitorEvent).order_by(VisitorEvent.occurred_at.desc()).limit(5000)
        if start_at is not None:
            statement = statement.where(VisitorEvent.occurred_at >= start_at)
        if end_at is not None:
            statement = statement.where(VisitorEvent.occurred_at <= end_at)
        return list(self.db.scalars(statement).all())

    def _list_user_messages(self, start_at: datetime | None = None, end_at: datetime | None = None) -> list[Message]:
        statement = select(Message).where(Message.role == "user").order_by(Message.created_at.desc()).limit(5000)
        if start_at is not None:
            statement = statement.where(Message.created_at >= start_at)
        if end_at is not None:
            statement = statement.where(Message.created_at <= end_at)
        return list(self.db.scalars(statement).all())

    def _count_unique_visitors(self, start_day: date, end_day: date) -> int:
        start_at, end_at = to_datetime_range(start_day, end_day)
        events = self._list_events(start_at, end_at)
        sessions = {event.session_id for event in events if event.session_id}
        if sessions:
            return len(sessions)
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(Conversation)
                .where(Conversation.started_at >= start_at, Conversation.started_at <= end_at)
            )
            or 0
        )

    def _questions_trend(self, messages: list[Message], days: int) -> list[dict[str, int]]:
        start_day = date.today() - timedelta(days=days - 1)
        counts = Counter(message.created_at.date().isoformat() for message in messages if message.created_at)
        return [
            {"date": (start_day + timedelta(days=index)).isoformat(), "count": counts.get((start_day + timedelta(days=index)).isoformat(), 0)}
            for index in range(days)
        ]

    def _daily_satisfaction(self, feedback_items: list[Feedback], days: int) -> list[dict[str, int | float | str]]:
        start_day = date.today() - timedelta(days=days - 1)
        grouped: dict[str, list[int]] = {}
        for item in feedback_items:
            if item.rating is None or item.created_at is None:
                continue
            grouped.setdefault(item.created_at.date().isoformat(), []).append(item.rating)
        rows: list[dict[str, int | float | str]] = []
        for index in range(days):
            day = (start_day + timedelta(days=index)).isoformat()
            ratings = grouped.get(day, [])
            rows.append({"date": day, "score": round(sum(ratings) / len(ratings), 2) if ratings else 0})
        return rows


def to_datetime_range(start_date: date | None, end_date: date | None) -> tuple[datetime | None, datetime | None]:
    start_at = datetime.combine(start_date, time.min) if start_date else None
    end_at = datetime.combine(end_date, time.max) if end_date else None
    return start_at, end_at


def normalize_question(content: str | None) -> str:
    return re.sub(r"\s+", "", (content or "").strip())[:80]


def extract_keywords(contents: list[str | None]) -> Counter[str]:
    stop_words = {"什么", "一下", "请问", "介绍", "怎么", "如何", "可以", "一个", "景区", "游客"}
    counter: Counter[str] = Counter()
    for content in contents:
        for term in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]+", content or ""):
            if term in stop_words or len(term) < 2:
                continue
            counter[term] += 1
    return counter
