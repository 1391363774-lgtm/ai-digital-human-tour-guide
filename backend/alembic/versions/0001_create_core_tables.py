"""创建核心业务表

Revision ID: 0001_create_core_tables
Revises: None
Create Date: 2026-07-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_create_core_tables"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="tourist"),
        sa.Column("age_group", sa.String(length=32), nullable=True),
        sa.Column("gender", sa.String(length=16), nullable=True),
        sa.Column("interests", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "scenic_spots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("scenic_area", sa.String(length=128), nullable=False, server_default="灵山胜境"),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("parameters", sa.Text(), nullable=True),
        sa.Column("core_function", sa.Text(), nullable=True),
        sa.Column("cultural_meaning", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("highlights", sa.Text(), nullable=True),
        sa.Column("open_info", sa.Text(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("recommended_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_scenic_spots_id", "scenic_spots", ["id"])
    op.create_index("ix_scenic_spots_code", "scenic_spots", ["code"], unique=True)
    op.create_index("ix_scenic_spots_name", "scenic_spots", ["name"])
    op.create_index("ix_scenic_spots_scenic_area", "scenic_spots", ["scenic_area"])
    op.create_index("ix_scenic_spots_category", "scenic_spots", ["category"])

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False, server_default="upload"),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_knowledge_documents_id", "knowledge_documents", ["id"])
    op.create_index("ix_knowledge_documents_title", "knowledge_documents", ["title"])
    op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"])
    op.create_index("ix_knowledge_documents_source_type", "knowledge_documents", ["source_type"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("knowledge_documents.id"), nullable=False),
        sa.Column("spot_id", sa.Integer(), sa.ForeignKey("scenic_spots.id"), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("vector_id", sa.String(length=255), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_knowledge_chunks_id", "knowledge_chunks", ["id"])
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_spot_id", "knowledge_chunks", ["spot_id"])
    op.create_index("ix_knowledge_chunks_vector_id", "knowledge_chunks", ["vector_id"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="web"),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("total_latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_conversations_id", "conversations", ["id"])
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_channel", "conversations", ["channel"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("audio_url", sa.String(length=500), nullable=True),
        sa.Column("sources_json", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_messages_id", "messages", ["id"])
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_role", "messages", ["role"])

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("interest", sa.String(length=64), nullable=False),
        sa.Column("duration_hours", sa.Integer(), nullable=True),
        sa.Column("group_type", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_recommendations_id", "recommendations", ["id"])
    op.create_index("ix_recommendations_user_id", "recommendations", ["user_id"])
    op.create_index("ix_recommendations_interest", "recommendations", ["interest"])

    op.create_table(
        "recommendation_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recommendation_id", sa.Integer(), sa.ForeignKey("recommendations.id"), nullable=False),
        sa.Column("spot_id", sa.Integer(), sa.ForeignKey("scenic_spots.id"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stay_minutes", sa.Integer(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
    )
    op.create_index("ix_recommendation_items_id", "recommendation_items", ["id"])
    op.create_index("ix_recommendation_items_recommendation_id", "recommendation_items", ["recommendation_id"])
    op.create_index("ix_recommendation_items_spot_id", "recommendation_items", ["spot_id"])

    op.create_table(
        "favorites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_favorites_id", "favorites", ["id"])
    op.create_index("ix_favorites_user_id", "favorites", ["user_id"])
    op.create_index("ix_favorites_target_type", "favorites", ["target_type"])
    op.create_index("ix_favorites_target_id", "favorites", ["target_id"])

    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("sentiment", sa.String(length=32), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_feedback_id", "feedback", ["id"])
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_index("ix_feedback_conversation_id", "feedback", ["conversation_id"])
    op.create_index("ix_feedback_sentiment", "feedback", ["sentiment"])

    op.create_table(
        "avatar_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("voice_name", sa.String(length=128), nullable=True),
        sa.Column("clothing", sa.String(length=128), nullable=True),
        sa.Column("style", sa.String(length=128), nullable=True),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_avatar_configs_id", "avatar_configs", ["id"])
    op.create_index("ix_avatar_configs_name", "avatar_configs", ["name"], unique=True)
    op.create_index("ix_avatar_configs_enabled", "avatar_configs", ["enabled"])

    op.create_table(
        "system_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("level", sa.String(length=32), nullable=False),
        sa.Column("module", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("extra_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_system_logs_id", "system_logs", ["id"])
    op.create_index("ix_system_logs_level", "system_logs", ["level"])
    op.create_index("ix_system_logs_module", "system_logs", ["module"])
    op.create_index("ix_system_logs_trace_id", "system_logs", ["trace_id"])


def downgrade() -> None:
    op.drop_table("system_logs")
    op.drop_table("avatar_configs")
    op.drop_table("feedback")
    op.drop_table("favorites")
    op.drop_table("recommendation_items")
    op.drop_table("recommendations")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_table("scenic_spots")
    op.drop_table("users")
