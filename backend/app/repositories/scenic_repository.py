from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.scenic import ScenicSpot
from app.schemas.scenic import ScenicSpotCreate, ScenicSpotUpdate


class ScenicSpotRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[ScenicSpot]:
        statement = select(ScenicSpot).order_by(ScenicSpot.id.asc())
        return list(self.db.scalars(statement).all())

    def list(self, keyword: str | None = None, limit: int = 100, offset: int = 0) -> list[ScenicSpot]:
        statement = select(ScenicSpot).order_by(ScenicSpot.id.asc()).limit(limit).offset(offset)
        if keyword:
            statement = statement.where(ScenicSpot.name.contains(keyword) | ScenicSpot.code.contains(keyword))
        return list(self.db.scalars(statement).all())

    def list_by_ids(self, ids: list[int]) -> list[ScenicSpot]:
        if not ids:
            return []
        statement = select(ScenicSpot).where(ScenicSpot.id.in_(ids))
        return list(self.db.scalars(statement).all())

    def get(self, spot_id: int) -> ScenicSpot | None:
        return self.db.get(ScenicSpot, spot_id)

    def create(self, payload: ScenicSpotCreate) -> ScenicSpot:
        spot = ScenicSpot(**payload.model_dump())
        self.db.add(spot)
        self.db.commit()
        self.db.refresh(spot)
        return spot

    def update(self, spot: ScenicSpot, payload: ScenicSpotUpdate) -> ScenicSpot:
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(spot, key, value)
        self.db.commit()
        self.db.refresh(spot)
        return spot

    def delete(self, spot: ScenicSpot) -> None:
        self.db.delete(spot)
        self.db.commit()
