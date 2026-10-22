"""Old unowned conversations remain private; no automatic claiming."""
from alembic import op
import sqlalchemy as sa

revision = "0005_visitor_scope"
down_revision = "0004_message_outcome"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("conversations", sa.Column("visitor_hash", sa.String(64), nullable=True))
    op.create_index("ix_conversations_visitor_hash", "conversations", ["visitor_hash"])


def downgrade():
    op.drop_index("ix_conversations_visitor_hash", table_name="conversations")
    with op.batch_alter_table("conversations") as batch:
        batch.drop_column("visitor_hash")
