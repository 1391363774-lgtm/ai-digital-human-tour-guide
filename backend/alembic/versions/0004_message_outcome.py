"""Distinguish complete, partial, refused, failed and cancelled answers."""
from alembic import op
import sqlalchemy as sa

revision = "0004_message_outcome"
down_revision = "0003_knowledge_revision"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("messages", sa.Column("status", sa.String(24), nullable=False, server_default="completed"))
    op.add_column("messages", sa.Column("request_id", sa.String(32), nullable=True))
    op.add_column("messages", sa.Column("error_code", sa.String(64), nullable=True))


def downgrade():
    with op.batch_alter_table("messages") as batch:
        batch.drop_column("error_code")
        batch.drop_column("request_id")
        batch.drop_column("status")
