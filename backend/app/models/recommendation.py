from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    interest: Mapped[str] = mapped_column(String(64), index=True)
    duration_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    group_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items = relationship("RecommendationItem", back_populates="recommendation", cascade="all, delete-orphan")


class RecommendationItem(Base):
    __tablename__ = "recommendation_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendations.id"), index=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("scenic_spots.id"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    stay_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recommendation = relationship("Recommendation", back_populates="items")
    spot = relationship("ScenicSpot", back_populates="recommendation_items")
