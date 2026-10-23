"""
数字人形象管理API - 真实持久化(外观/声音/行为配置)
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import AvatarConfig

router = APIRouter()

DEFAULT_AVATARS = [
    {"name": "灵小仙·修仙版", "style": "修仙者", "voice": "zh-CN-XiaoxiaoNeural",
     "appearance": {"robe": "白金修仙长袍", "hair": "高髻", "accessory": "金色莲花",
                    "theme_color": "#C5A55A", "background": "灵山梵宫"},
     "is_active": 1},
    {"name": "灵小仙·禅服版", "style": "禅意", "voice": "zh-CN-XiaoyiNeural",
     "appearance": {"robe": "素色禅服", "hair": "低髻", "accessory": "木质佛珠",
                    "theme_color": "#8A7130", "background": "祥符禅寺"},
     "is_active": 0},
    {"name": "灵小仙·现代版", "style": "现代", "voice": "zh-CN-YunxiNeural",
     "appearance": {"robe": "现代导览制服", "hair": "束发", "accessory": "耳麦",
                    "theme_color": "#3D5678", "background": "拈花湾"},
     "is_active": 0},
]


async def _seed_if_empty(db: AsyncSession):
    count = (await db.execute(select(AvatarConfig))).scalars().all()
    if not count:
        for a in DEFAULT_AVATARS:
            db.add(AvatarConfig(**a))
        await db.commit()


@router.get("/list")
async def list_avatars(db: AsyncSession = Depends(get_db)):
    await _seed_if_empty(db)
    rows = (await db.execute(select(AvatarConfig))).scalars().all()
    return {"avatars": [{
        "id": r.id, "name": r.name, "style": r.style, "voice": r.voice,
        "appearance": r.appearance, "is_active": bool(r.is_active),
    } for r in rows]}


@router.get("/config")
async def get_active_config(db: AsyncSession = Depends(get_db)):
    """获取当前启用的数字人配置(游客端加载)"""
    await _seed_if_empty(db)
    row = (await db.execute(
        select(AvatarConfig).where(AvatarConfig.is_active == 1).limit(1)
    )).scalar_one_or_none()
    if not row:
        row = (await db.execute(select(AvatarConfig).limit(1))).scalar_one()
    return {
        "id": row.id, "name": row.name, "style": row.style, "voice": row.voice,
        "appearance": row.appearance,
        "behavior": {"greeting": "阿弥陀佛,欢迎来到灵山胜境!我是您的AI导游灵小仙,"
                                 "对这里的每一处景点都了如指掌,有什么可以帮您的?",
                     "auto_greeting": True},
    }


class AvatarUpdate(BaseModel):
    name: Optional[str] = None
    voice: Optional[str] = None
    appearance: Optional[dict] = None


@router.put("/config/{avatar_id}")
async def update_avatar(avatar_id: int, req: AvatarUpdate,
                        db: AsyncSession = Depends(get_db)):
    row = await db.get(AvatarConfig, avatar_id)
    if not row:
        return {"ok": False, "message": "数字人不存在"}
    if req.name:
        row.name = req.name
    if req.voice:
        row.voice = req.voice
    if req.appearance:
        merged = dict(row.appearance or {})
        merged.update(req.appearance)
        row.appearance = merged
    await db.commit()
    return {"ok": True, "message": "配置已更新,游客端即时生效"}


@router.post("/activate/{avatar_id}")
async def activate_avatar(avatar_id: int, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(AvatarConfig))).scalars().all()
    found = False
    for r in rows:
        r.is_active = 1 if r.id == avatar_id else 0
        found = found or r.id == avatar_id
    if not found:
        return {"ok": False, "message": "数字人不存在"}
    await db.commit()
    return {"ok": True, "message": "已切换数字人形象"}
