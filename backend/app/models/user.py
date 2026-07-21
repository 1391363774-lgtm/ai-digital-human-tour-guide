from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="tourist", index=True)
    age_group: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    interests: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    conversations = relationship("Conversation", back_populates="user")
    favorites = relationship("Favorite", back_populates="user")
    feedback_items = relationship("Feedback", back_populates="user")
    visitor_events = relationship("VisitorEvent", back_populates="user")
