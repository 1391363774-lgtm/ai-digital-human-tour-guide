from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.favorite_repository import FavoriteRepository
from app.schemas.favorite import FavoriteCreate, FavoriteOut
from app.schemas.response import success

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


@router.post("")
def create_favorite(payload: FavoriteCreate, db: Session = Depends(get_db)):
    favorite = FavoriteRepository(db).create(payload)
    return success(FavoriteOut.model_validate(favorite).model_dump())


@router.get("")
def list_favorites(db: Session = Depends(get_db)):
    favorites = FavoriteRepository(db).list()
    return success([FavoriteOut.model_validate(item).model_dump() for item in favorites])


@router.delete("/{favorite_id}")
def delete_favorite(favorite_id: int, db: Session = Depends(get_db)):
    deleted = FavoriteRepository(db).delete(favorite_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="收藏不存在")
    return success({"deleted": True})
