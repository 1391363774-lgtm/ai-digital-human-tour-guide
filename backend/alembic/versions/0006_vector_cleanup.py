"""Durable cleanup of vectors no longer referenced by committed SQL."""
from alembic import op
import sqlalchemy as sa

revision = "0006_vector_cleanup"
down_revision = "0005_visitor_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pending_vector_cleanup",
        sa.Column("vector_id", sa.String(255), primary_key=True),
        sa.Column("collection_name", sa.String(255), nullable=False),
    )


def downgrade():
    op.drop_table("pending_vector_cleanup")
