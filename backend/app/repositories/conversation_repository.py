from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from fastapi import HTTPException

from app.models.conversation import Conversation, Message


class ConversationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _owned(self, statement):
        owner = self.db.info.get("visitor")
        return statement.where(Conversation.visitor_hash == owner) if owner else statement

    def get_or_create(self, conversation_id: int | None, title: str | None = None) -> Conversation:
        if conversation_id is not None:
            conversation = self.db.scalar(self._owned(select(Conversation).where(Conversation.id == conversation_id)))
            if conversation is not None:
                return conversation
            raise HTTPException(404, "会话不存在")

        conversation = Conversation(title=title[:255] if title else None, channel="web", visitor_hash=self.db.info.get("visitor"))
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def add_message(
        self,
        conversation: Conversation,
        role: str,
        content: str,
        sources: list[dict] | None = None,
        latency_ms: int = 0,
        audio_url: str | None = None,
        status: str = "completed",
        request_id: str | None = None,
        error_code: str | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation.id,
            role=role,
            content=content,
            audio_url=audio_url,
            sources_json=json.dumps(sources or [], ensure_ascii=False),
            latency_ms=latency_ms,
            status=status,
            request_id=request_id,
            error_code=error_code,
        )
        self.db.add(message)
        conversation.total_latency_ms = (conversation.total_latency_ms or 0) + latency_ms
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_conversations(self, limit: int = 20, offset: int = 0) -> list[Conversation]:
        statement = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .order_by(Conversation.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(self._owned(statement)).all())

    def get_with_messages(self, conversation_id: int) -> Conversation | None:
        statement = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.id == conversation_id)
        )
        return self.db.scalar(self._owned(statement))

    def list_recent_messages(self, conversation_id: int, limit: int = 6) -> list[Message]:
        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        messages = list(self.db.scalars(statement).all())
        return list(reversed(messages))
