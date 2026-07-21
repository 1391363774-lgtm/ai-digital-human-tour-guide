from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
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
    if not payload.sentiment:
        analysis = analysis_service.analyze(content=payload.content, rating=payload.rating)
        payload = payload.model_copy(update={"sentiment": analysis.sentiment})
    feedback = FeedbackRepository(db).create(payload)
    return success(FeedbackOut.model_validate(feedback).model_dump())


@router.post("/analyze")
def analyze_feedback(payload: FeedbackAnalysisRequest):
    analysis = analysis_service.analyze(content=payload.content, rating=payload.rating)
    return success(FeedbackAnalysisOut(**analysis.__dict__).model_dump())


@router.get("/stats")
def feedback_stats(db: Session = Depends(get_db)):
    feedback_items = FeedbackRepository(db).list(limit=1000, offset=0)
    stats = analysis_service.summarize(feedback_items)
    return success(FeedbackStatsOut(**stats).model_dump())


@router.get("")
def list_feedback(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    feedback_items = FeedbackRepository(db).list(limit=limit, offset=offset)
    return success([FeedbackOut.model_validate(item).model_dump() for item in feedback_items])
