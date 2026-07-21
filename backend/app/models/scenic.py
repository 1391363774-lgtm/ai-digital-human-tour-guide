from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ScenicSpot(Base):
    __tablename__ = "scenic_spots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    scenic_area: Mapped[str] = mapped_column(String(128), default="灵山胜境", index=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    parameters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    core_function: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cultural_meaning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    highlights: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    open_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_duration_minutes: Mapped[Optional[int]] = mapped_column(nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    knowledge_chunks = relationship("KnowledgeChunk", back_populates="spot")
    recommendation_items = relationship("RecommendationItem", back_populates="spot")
