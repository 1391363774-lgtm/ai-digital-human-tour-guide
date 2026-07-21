from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.feedback import Feedback
from app.schemas.feedback import FeedbackCreate


class FeedbackRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: FeedbackCreate, user_id: int | None = None) -> Feedback:
        feedback = Feedback(
            user_id=user_id,
            conversation_id=payload.conversation_id,
            rating=payload.rating,
            sentiment=payload.sentiment,
            content=payload.content,
        )
        self.db.add(feedback)
        self.db.commit()
        self.db.refresh(feedback)
        return feedback

    def list(self, limit: int = 100, offset: int = 0) -> list[Feedback]:
        statement = select(Feedback).order_by(Feedback.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(statement).all())
