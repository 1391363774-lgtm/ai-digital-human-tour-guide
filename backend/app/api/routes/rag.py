from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.rag import RagSearchHitOut, RagSearchRequest, RagSearchResponse
from app.schemas.response import success
from app.services.rag_service import RagService

router = APIRouter(prefix="/api/rag", tags=["rag"])


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
