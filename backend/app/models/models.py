from sqlalchemy import Column, Integer, String, Text, Float, DateTime, JSON
from sqlalchemy.sql import func

from app.core.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tourist_id = Column(String(64), index=True)
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
    tourist_id = Column(String(64))
    question = Column(Text)
    answer = Column(Text)
    satisfaction = Column(Integer, nullable=True)      # 1-5分,游客主动评价
    sentiment = Column(String(20))  # positive / neutral / negative (系统自动判)
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


class SpotVisit(Base):
    """景点扫码签到定位(GPS弱信号场景的替代定位方案)"""
    __tablename__ = "spot_visits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tourist_id = Column(String(64), index=True)
    spot_id = Column(String(20))
    spot_name = Column(String(100))
    method = Column(String(20), default="qrcode")  # qrcode / bluetooth / manual
    created_at = Column(DateTime, server_default=func.now())


class KnowledgeRevision(Base):
    __tablename__ = 'knowledge_revision'
    id = Column(Integer, primary_key=True)
    value = Column(Integer, nullable=False, default=0)
    chunk_size = Column(Integer, nullable=False, default=800)
    overlap = Column(Integer, nullable=False, default=80)
