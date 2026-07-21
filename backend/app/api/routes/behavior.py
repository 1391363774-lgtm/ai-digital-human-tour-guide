from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.behavior_repository import VisitorEventRepository, visitor_event_to_dict
from app.schemas.behavior import (
    VisitorEventCreate,
    VisitorEventImportResult,
    VisitorEventOut,
    VisitorEventStatsOut,
)
from app.schemas.response import success
from app.services.behavior_import_service import BehaviorImportError, BehaviorImportService

router = APIRouter(prefix="/api/behavior", tags=["behavior"])


@router.post("/events")
def create_visitor_event(payload: VisitorEventCreate, db: Session = Depends(get_db)):
    event = VisitorEventRepository(db).create(payload)
    return success(VisitorEventOut(**visitor_event_to_dict(event)).model_dump())


@router.get("/events")
def list_visitor_events(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    events = VisitorEventRepository(db).list(limit=limit, offset=offset)
    return success([VisitorEventOut(**visitor_event_to_dict(event)).model_dump() for event in events])


@router.post("/import")
async def import_visitor_events(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="仅支持 CSV 行为数据文件")
    raw_bytes = await file.read()
    try:
        payloads, errors = BehaviorImportService().parse_csv(raw_bytes)
    except BehaviorImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    imported = VisitorEventRepository(db).bulk_create(payloads) if payloads else []
    result = VisitorEventImportResult(
        imported_count=len(imported),
        skipped_count=len(errors),
        errors=errors[:20],
    )
    return success(result.model_dump())


@router.get("/stats")
def visitor_event_stats(db: Session = Depends(get_db)):
    stats = VisitorEventRepository(db).stats()
    return success(VisitorEventStatsOut(**stats).model_dump())
