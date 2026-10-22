from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.rag import RagSearchHitOut, RagSearchRequest, RagSearchResponse
from app.schemas.response import success
from app.services.rag_service import RagService, source_for_chunk
from app.models.knowledge import KnowledgeChunk

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.get("/sources/{chunk_id}")
def read_evidence(chunk_id: int, db: Session = Depends(get_db)):
    chunk = db.get(KnowledgeChunk, chunk_id)
    if chunk is None:
        raise HTTPException(404, "片段不存在或已更新，请重新提问")
    return success({"content": chunk.content, "source": source_for_chunk(chunk, "evidence_lookup")})


@router.post("/search")
def search_knowledge(
    payload: RagSearchRequest,
    db: Session = Depends(get_db),
):
    service = RagService(db)
    hits = service.search(payload.query, top_k=payload.top_k)
    context = service.build_context(payload.query, top_k=payload.top_k)
    data = RagSearchResponse(
        query=payload.query,
        hits=[
            RagSearchHitOut(content=hit.content, score=hit.score, source=hit.source)
            for hit in hits
        ],
        context=context,
    )
    return success(data.model_dump())
