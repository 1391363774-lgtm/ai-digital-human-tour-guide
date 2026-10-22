import json
import asyncio
import logging
import time
from uuid import uuid4
from contextlib import aclosing

import anyio
from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.access import get_visitor_db as get_db
from app.core.streaming import ClosingStreamingResponse as TextStreamingResponse
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse, ChatSourceOut
from app.schemas.response import success
from app.services.chat_service import ChatService
from app.services.llm_client import LLMClientError, get_llm_client

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


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
    started_at = time.perf_counter()
    request_id = uuid4().hex
    service = ChatService(db)
    def prepare():
        result = service.prepare_stream(payload.message, payload.top_k, payload.conversation_id, payload.fast)
        # Snapshot the scalar in the worker: an expired ORM object may issue SQL.
        return result, result[0].id
    (conversation, messages, hits, refusal, fast_answer), conversation_id = await run_in_threadpool(prepare)

    def event(kind, **fields):
        return f"data: {json.dumps({'type': kind, 'request_id': request_id, **fields}, ensure_ascii=False)}\n\n"

    async def event_stream():
        full_text = ""
        status = "cancelled"
        error_code = None
        first_text_ms = None
        client = None
        try:
            yield event("conversation_id", id=conversation_id)
            yield event("source", sources=[{"content": h.content[:500], "score": h.score, "metadata": h.source} for h in hits])
            if refusal or fast_answer:
                full_text = refusal or fast_answer
                first_text_ms = int((time.perf_counter() - started_at) * 1000)
                yield event("refused" if refusal else "text", text=full_text)
                status = "refused" if refusal else "completed"
            else:
                client = get_llm_client()
                async with aclosing(client.achat_stream(messages)) as stream:
                    async for chunk in stream:
                        if chunk.strip() and first_text_ms is None:
                            first_text_ms = int((time.perf_counter() - started_at) * 1000)
                        full_text += chunk
                        yield event("text", text=chunk)
                if not full_text.strip():
                    raise LLMClientError("empty stream")
                status = "completed"
        except (asyncio.CancelledError, GeneratorExit):
            status, error_code = "cancelled", "client_disconnected"
            raise
        except Exception as exc:
            status = "partial" if full_text.strip() else "failed"
            error_code = "model_unavailable" if isinstance(exc, LLMClientError) else "internal_error"
            logger.warning("chat_stream_failed request_id=%s exception_type=%s", request_id, type(exc).__name__)
            yield event("error", text="回答未完成，请重试。" if full_text else "服务暂时不可用，请重试。",
                        code=error_code, partial=bool(full_text.strip()), retryable=True)
        finally:
            # A single sequential Session user; cancellation must not interrupt the audit write.
            with anyio.CancelScope(shield=True):
                await run_in_threadpool(service.persist_stream_answer, conversation, full_text, hits, started_at,
                                        status=status, request_id=request_id, error_code=error_code)
            logger.info("chat_stream_finished request_id=%s status=%s first_text_ms=%s total_ms=%s",
                        request_id, status, first_text_ms, int((time.perf_counter() - started_at) * 1000))
        yield event("done", conversation_id=conversation_id, status=status, first_text_ms=first_text_ms,
                    provider=getattr(client, "selected_provider", None) or getattr(client, "provider", "local_fast_rag" if fast_answer else "rule"),
                    model=getattr(client, "selected_model", None) or getattr(client, "model", "extractive-guide-v1" if fast_answer else "refusal"),
                    fallback_from=getattr(client, "failed_providers", []),
                    total_ms=int((time.perf_counter() - started_at) * 1000))

    return TextStreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "X-Request-ID": request_id,
        },
    )
