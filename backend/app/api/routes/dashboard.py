from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.dashboard import DashboardOverviewOut
from app.schemas.response import success
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
def dashboard_overview(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    overview = DashboardService(db).overview(start_date=start_date, end_date=end_date)
    return success(DashboardOverviewOut(**overview).model_dump())
