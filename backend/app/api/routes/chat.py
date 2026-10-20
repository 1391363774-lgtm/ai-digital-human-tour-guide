import json
import asyncio
import logging
import time
from contextlib import aclosing

import anyio
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse, ChatSourceOut
from app.schemas.response import success
from app.services.chat_service import ChatService
from app.services.llm_client import LLMClientError, get_llm_client

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


class TextStreamingResponse(StreamingResponse):
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            # ASGI 2.4 may fail during send(), while our generator is suspended
            # at yield. Explicitly close it instead of waiting for Python GC.
            with anyio.CancelScope(shield=True):
                await self.body_iterator.aclose()


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
    """Incremental text with async model I/O and disconnect cleanup."""
    service = ChatService(db)
    conversation, messages, hits, refusal, fast_answer = await run_in_threadpool(
        service.prepare_stream,
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
            await run_in_threadpool(service.persist_stream_answer, conversation, fast_answer, hits, started_at)
            yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation.id})}\n\n"
            return

        llm_client = get_llm_client()
        full_text = ""
        try:
            async with aclosing(llm_client.achat_stream(messages)) as stream:
                async for chunk in stream:
                    full_text += chunk
                    yield f"data: {json.dumps({'type': 'text', 'text': chunk})}\n\n"
        except asyncio.CancelledError:
            logger.info("text_stream_cancelled conversation_id=%s", conversation.id)
            raise
        except LLMClientError as exc:
            yield f"data: {json.dumps({'type': 'error', 'text': str(exc)})}\n\n"

        # 保留已生成文本；异常文案不覆盖已输出的部分回答。
        if full_text:
            await run_in_threadpool(service.persist_stream_answer, conversation, full_text, hits, started_at)

        yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation.id})}\n\n"

    return TextStreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
