from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.core.database import get_db
from app.models.models import KnowledgeItem

router = APIRouter()


class KnowledgeCreate(BaseModel):
    category: str
    title: str
    content: str
    source: str = "manual"
    status: str = "draft"


class KnowledgeUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None


@router.get("/items")
async def get_knowledge(
    category: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    query = select(KnowledgeItem)
    if category:
        query = query.where(KnowledgeItem.category == category)
    if status:
        query = query.where(KnowledgeItem.status == status)
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()
    return {
        "items": [
            {
                "id": i.id,
                "category": i.category,
                "title": i.title,
                "content": i.content[:100],
                "source": i.source,
                "status": i.status,
                "updated_at": str(i.updated_at),
            }
            for i in items
        ],
        "total": len(items),
    }


@router.post("/items")
async def create_knowledge(data: KnowledgeCreate, db: AsyncSession = Depends(get_db)):
    item = KnowledgeItem(**data.dict())
    db.add(item)
    await db.commit()
    return {"id": item.id, "message": "创建成功"}


@router.put("/items/{item_id}")
async def update_knowledge(item_id: int, data: KnowledgeUpdate, db: AsyncSession = Depends(get_db)):
    query = select(KnowledgeItem).where(KnowledgeItem.id == item_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "知识条目不存在")
    for key, value in data.dict(exclude_unset=True).items():
        setattr(item, key, value)
    item.updated_at = datetime.now()
    await db.commit()
    return {"message": "更新成功"}


@router.delete("/items/{item_id}")
async def delete_knowledge(item_id: int, db: AsyncSession = Depends(get_db)):
    query = delete(KnowledgeItem).where(KnowledgeItem.id == item_id)
    await db.execute(query)
    await db.commit()
    return {"message": "删除成功"}


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func

    total = await db.execute(select(func.count(KnowledgeItem.id)))
    published = await db.execute(
        select(func.count(KnowledgeItem.id)).where(KnowledgeItem.status == "published")
    )
    categories = await db.execute(
        select(KnowledgeItem.category, func.count(KnowledgeItem.id)).group_by(
            KnowledgeItem.category
        )
    )
    return {
        "total": total.scalar(),
        "published": published.scalar(),
        "categories": [{"name": c[0], "count": c[1]} for c in categories.all()],
    }
