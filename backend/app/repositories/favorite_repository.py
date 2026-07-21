from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.favorite import Favorite
from app.models.user import User
from app.schemas.favorite import FavoriteCreate


class FavoriteRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create_anonymous_user(self) -> User:
        user = self.db.scalar(select(User).where(User.username == "anonymous"))
        if user is not None:
            return user
        user = User(username="anonymous", role="tourist")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def create(self, payload: FavoriteCreate, user_id: int | None = None) -> Favorite:
        if user_id is None:
            user_id = self.get_or_create_anonymous_user().id

        existing = self.db.scalar(
            select(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.target_type == payload.target_type,
                Favorite.target_id == payload.target_id,
            )
        )
        if existing is not None:
            return existing

        favorite = Favorite(
            user_id=user_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
        )
        self.db.add(favorite)
        self.db.commit()
        self.db.refresh(favorite)
        return favorite

    def list(self, user_id: int | None = None) -> list[Favorite]:
        if user_id is None:
            user_id = self.get_or_create_anonymous_user().id
        statement = select(Favorite).where(Favorite.user_id == user_id).order_by(Favorite.created_at.desc())
        return list(self.db.scalars(statement).all())

    def delete(self, favorite_id: int, user_id: int | None = None) -> bool:
        if user_id is None:
            user_id = self.get_or_create_anonymous_user().id
        favorite = self.db.scalar(
            select(Favorite).where(Favorite.id == favorite_id, Favorite.user_id == user_id)
        )
        if favorite is None:
            return False
        self.db.delete(favorite)
        self.db.commit()
        return True
