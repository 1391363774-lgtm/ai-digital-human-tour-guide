from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AvatarConfig(Base):
    __tablename__ = "avatar_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    voice_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    clothing: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    style: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
