"""Database generation avoids process-local invalidation gaps across workers."""
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeRevision


def bump_knowledge_revision(db: Session) -> None:
    """Call BEFORE committing the same transaction as a knowledge mutation."""
    result = db.execute(
        update(KnowledgeRevision).where(KnowledgeRevision.id == 1)
        .values(revision=KnowledgeRevision.revision + 1)
    )
    if result.rowcount != 1:
        raise RuntimeError("knowledge_revision 未初始化，请运行 alembic upgrade head")


def retrieval_generation(db: Session) -> tuple[object, int]:
    bind = db.get_bind()
    engine = getattr(bind, "engine", bind)
    # A fresh connection sees committed revisions even if this Session already
    # has a transaction/snapshot. Do not commit or rollback the caller's Session.
    with engine.connect() as connection:
        revision = connection.scalar(select(KnowledgeRevision.revision).where(KnowledgeRevision.id == 1))
    if revision is None:
        raise RuntimeError("knowledge_revision 未初始化，请运行 alembic upgrade head")
    # Keep the engine itself in the bounded key space: a bare id(engine) could
    # later be reused for an unrelated in-memory/test database.
    return engine, revision
