import json
import time

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse, ChatSourceOut
from app.schemas.response import success
from app.services.chat_service import ChatService
from app.services.llm_client import ChatMessage, LLMClientError, get_llm_client

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/messages")
async def create_chat_message(
    payload: ChatMessageRequest,
    db: Session = Depends(get_db),
):
    answer = await run_in_threadpool(
        ChatService(db).answer,
        payload.message,
        payload.top_k,
        payload.conversation_id,
        payload.fast,
    )
    data = ChatMessageResponse(
        answer=answer.answer,
        provider=answer.provider,
        model=answer.model,
        conversation_id=answer.conversation_id,
        refused=answer.refused,
        sources=[
            ChatSourceOut(
                content=hit.content[:500],
                score=hit.score,
                metadata=hit.source,
            )
            for hit in answer.sources
        ],
    )
    return success(data.model_dump())


@router.post("/stream")
async def chat_stream(
    payload: ChatMessageRequest,
    db: Session = Depends(get_db),
):
    """SSE 流式回答：首 token 在 ~1s 内到达，边生成边推送。"""
    service = ChatService(db)
    conversation, messages, hits, refusal, fast_answer = service.prepare_stream(
        payload.message, payload.top_k, payload.conversation_id, payload.fast,
    )
    started_at = time.perf_counter()

    async def event_stream():
        if refusal:
            yield f"data: {json.dumps({'type': 'refused', 'text': refusal})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation.id})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'conversation_id', 'id': conversation.id})}\n\n"

        if fast_answer:
            yield f"data: {json.dumps({'type': 'text', 'text': fast_answer})}\n\n"
            service.persist_stream_answer(conversation, fast_answer, hits, started_at)
            yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation.id})}\n\n"
            return

        llm_client = get_llm_client()
        full_text = ""
        try:
            for chunk in llm_client.chat_stream(messages):
                full_text += chunk
                yield f"data: {json.dumps({'type': 'text', 'text': chunk})}\n\n"
        except LLMClientError as exc:
            full_text = f"AI 模型暂时不可用：{exc}"
            yield f"data: {json.dumps({'type': 'error', 'text': str(exc)})}\n\n"

        # 持久化完整回答
        if full_text:
            service.persist_stream_answer(conversation, full_text, hits, started_at)

        yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation.id})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
