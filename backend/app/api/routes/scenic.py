from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.scenic_repository import ScenicSpotRepository
from app.schemas.response import success
from app.schemas.scenic import ScenicSpotCreate, ScenicSpotOut, ScenicSpotUpdate

router = APIRouter(prefix="/api", tags=["scenic"])


@router.get("/spots")
def list_public_spots(
    keyword: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    spots = ScenicSpotRepository(db).list(keyword=keyword, limit=limit, offset=offset)
    return success([ScenicSpotOut.model_validate(item).model_dump() for item in spots])


@router.post("/admin/spots")
def create_spot(payload: ScenicSpotCreate, db: Session = Depends(get_db)):
    spot = ScenicSpotRepository(db).create(payload)
    return success(ScenicSpotOut.model_validate(spot).model_dump())


@router.put("/admin/spots/{spot_id}")
def update_spot(spot_id: int, payload: ScenicSpotUpdate, db: Session = Depends(get_db)):
    repository = ScenicSpotRepository(db)
    spot = repository.get(spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    updated = repository.update(spot, payload)
    return success(ScenicSpotOut.model_validate(updated).model_dump())


@router.delete("/admin/spots/{spot_id}")
def delete_spot(spot_id: int, db: Session = Depends(get_db)):
    repository = ScenicSpotRepository(db)
    spot = repository.get(spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    repository.delete(spot)
    return success({"deleted": True})
