from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.response import success
from app.schemas.route import RouteRecommendRequest, RouteRecommendResponse, RouteSpotOut
from app.services.route_service import RouteRecommendationService

router = APIRouter(prefix="/api/routes", tags=["routes"])


@router.post("/recommend")
def recommend_route(
    payload: RouteRecommendRequest,
    db: Session = Depends(get_db),
):
    result = RouteRecommendationService(db).recommend(
        interest=payload.interest,
        duration_hours=payload.duration_hours,
        group_type=payload.group_type,
    )
    data = RouteRecommendResponse(
        recommendation_id=result.recommendation_id,
        interest=result.interest,
        duration_hours=result.duration_hours,
        group_type=result.group_type,
        reason=result.reason,
        spots=[
            RouteSpotOut(
                spot_id=item.spot.id,
                name=item.spot.name,
                category=item.spot.category,
                stay_minutes=item.stay_minutes,
                explanation=item.explanation,
                highlights=item.spot.highlights,
            )
            for item in result.spots
        ],
    )
    return success(data.model_dump())
