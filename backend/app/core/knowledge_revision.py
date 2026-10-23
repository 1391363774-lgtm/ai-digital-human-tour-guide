from sqlalchemy import update
from app.models.models import KnowledgeRevision


async def bump_revision(db, **settings):
    await db.execute(update(KnowledgeRevision).where(KnowledgeRevision.id==1).values(value=KnowledgeRevision.value+1,**settings))
