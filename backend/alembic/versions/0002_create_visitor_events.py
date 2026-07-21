"""创建游客行为事件表

Revision ID: 0002_create_visitor_events
Revises: 0001_create_core_tables
Create Date: 2026-07-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_create_visitor_events"
down_revision: Union[str, None] = "0001_create_core_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "visitor_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("spot_id", sa.Integer(), sa.ForeignKey("scenic_spots.id"), nullable=True),
        sa.Column("page_path", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_visitor_events_id", "visitor_events", ["id"])
    op.create_index("ix_visitor_events_user_id", "visitor_events", ["user_id"])
    op.create_index("ix_visitor_events_session_id", "visitor_events", ["session_id"])
    op.create_index("ix_visitor_events_event_type", "visitor_events", ["event_type"])
    op.create_index("ix_visitor_events_target_type", "visitor_events", ["target_type"])
    op.create_index("ix_visitor_events_target_id", "visitor_events", ["target_id"])
    op.create_index("ix_visitor_events_spot_id", "visitor_events", ["spot_id"])
    op.create_index("ix_visitor_events_source", "visitor_events", ["source"])
    op.create_index("ix_visitor_events_occurred_at", "visitor_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("visitor_events")
