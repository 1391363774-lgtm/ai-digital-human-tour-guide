from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.history import ConversationDetailOut, ConversationOut, MessageOut
from app.schemas.response import success

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
def list_history(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    conversations = ConversationRepository(db).list_conversations(limit=limit, offset=offset)
    data = [
        ConversationOut(
            id=item.id,
            title=item.title,
            channel=item.channel,
            total_latency_ms=item.total_latency_ms,
            started_at=item.started_at,
            message_count=len(item.messages),
        ).model_dump()
        for item in conversations
    ]
    return success(data)


@router.get("/{conversation_id}")
def get_history_detail(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    conversation = ConversationRepository(db).get_with_messages(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    data = ConversationDetailOut(
        id=conversation.id,
        title=conversation.title,
        channel=conversation.channel,
        total_latency_ms=conversation.total_latency_ms,
        started_at=conversation.started_at,
        messages=[MessageOut.model_validate(item) for item in conversation.messages],
    )
    return success(data.model_dump())
