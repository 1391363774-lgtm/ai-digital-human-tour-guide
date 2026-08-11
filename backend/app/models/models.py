from sqlalchemy import Column, Integer, String, Text, Float, DateTime, JSON, Enum
from sqlalchemy.sql import func

from app.core.database import Base

import enum


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tourist_id = Column(String(50), index=True)
    created_at = Column(DateTime, server_default=func.now())


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, index=True)
    role = Column(String(20))  # user / assistant
    content = Column(Text)
    audio_url = Column(String(500), nullable=True)
    intent = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class TouristFeedback(Base):
    __tablename__ = "tourist_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tourist_id = Column(String(50))
    question = Column(Text)
    answer = Column(Text)
    satisfaction = Column(Integer)
    sentiment = Column(String(20))  # positive / neutral / negative
    created_at = Column(DateTime, server_default=func.now())


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(50))
    title = Column(String(200))
    content = Column(Text)
    source = Column(String(100))
    status = Column(String(20), default="draft")  # draft / published
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AvatarConfig(Base):
    __tablename__ = "avatar_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50))
    style = Column(String(50))
    voice = Column(String(50))
    appearance = Column(JSON)
    is_active = Column(Integer, default=0)
