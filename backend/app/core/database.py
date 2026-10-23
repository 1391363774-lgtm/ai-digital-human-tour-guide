"""
数据库连接 - 默认SQLite(aiosqlite),exe双击即跑,无需安装MySQL。
如需MySQL,仅需在 .env 将 DATABASE_URL 改为:
  mysql+aiomysql://root:密码@localhost:3306/lingshan_guide
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    """建表(幂等)"""
    from app.models import models  # noqa: F401 - 确保模型已注册
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    from app.models.models import KnowledgeRevision
    from sqlalchemy.exc import IntegrityError
    async with async_session() as db:
        if await db.get(KnowledgeRevision, 1) is None:
            db.add(KnowledgeRevision(id=1,value=0,chunk_size=800,overlap=80))
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()  # another worker seeded the same singleton
