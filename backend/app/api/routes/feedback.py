from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.access import get_visitor_db as get_db, require_admin
from app.repositories.conversation_repository import ConversationRepository
from fastapi import HTTPException
from app.repositories.feedback_repository import FeedbackRepository
from app.schemas.feedback import (
    FeedbackAnalysisOut,
    FeedbackAnalysisRequest,
    FeedbackCreate,
    FeedbackOut,
    FeedbackStatsOut,
)
from app.schemas.response import success
from app.services.feedback_analysis_service import FeedbackAnalysisService

router = APIRouter(prefix="/api/feedback", tags=["feedback"])
analysis_service = FeedbackAnalysisService()


@router.post("")
def create_feedback(payload: FeedbackCreate, db: Session = Depends(get_db)):
    if payload.conversation_id is not None and ConversationRepository(db).get_with_messages(payload.conversation_id) is None:
        raise HTTPException(404, "会话不存在")
    if not payload.sentiment:
        analysis = analysis_service.analyze(content=payload.content, rating=payload.rating)
        payload = payload.model_copy(update={"sentiment": analysis.sentiment})
    feedback = FeedbackRepository(db).create(payload)
    return success(FeedbackOut.model_validate(feedback).model_dump())


@router.post("/analyze")
def analyze_feedback(payload: FeedbackAnalysisRequest):
    analysis = analysis_service.analyze(content=payload.content, rating=payload.rating)
    return success(FeedbackAnalysisOut(**analysis.__dict__).model_dump())


@router.get("/stats", dependencies=[Depends(require_admin)])
def feedback_stats(db: Session = Depends(get_db)):
    feedback_items = FeedbackRepository(db).list(limit=1000, offset=0)
    stats = analysis_service.summarize(feedback_items)
    return success(FeedbackStatsOut(**stats).model_dump())


@router.get("", dependencies=[Depends(require_admin)])
def list_feedback(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    feedback_items = FeedbackRepository(db).list(limit=limit, offset=offset)
    return success([FeedbackOut.model_validate(item).model_dump() for item in feedback_items])
