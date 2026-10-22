"""Shared retrieval generation, seeded for existing deployments."""
from alembic import op
import sqlalchemy as sa

revision = "0003_knowledge_revision"
down_revision = "0002_create_visitor_events"
branch_labels = None
depends_on = None


def upgrade():
    table = op.create_table(
        "knowledge_revision",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
    )
    op.bulk_insert(table, [{"id": 1, "revision": 0}])


def downgrade():
    op.drop_table("knowledge_revision")
