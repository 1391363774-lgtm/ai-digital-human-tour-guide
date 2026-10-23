"""
数据分析API - 全部来自真实交互数据(SQLite聚合)
支撑管理后台:数据大屏 + 游客感受度报告
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import ChatMessage, TouristFeedback, SpotVisit

router = APIRouter()


# ---------------- 数据大屏 ----------------
@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)

    # 今日服务人次(按游客去重)
    today_visitors = (await db.execute(
        select(func.count(distinct(TouristFeedback.tourist_id)))
        .where(TouristFeedback.created_at >= today))).scalar() or 0
    # 今日问答轮次
    today_qa = (await db.execute(
        select(func.count(TouristFeedback.id))
        .where(TouristFeedback.created_at >= today))).scalar() or 0
    # 本周问答
    week_qa = (await db.execute(
        select(func.count(TouristFeedback.id))
        .where(TouristFeedback.created_at >= week_ago))).scalar() or 0
    # 满意度(主动评分均分,5分制)
    avg_sat = (await db.execute(
        select(func.avg(TouristFeedback.satisfaction))
        .where(TouristFeedback.satisfaction.isnot(None)))).scalar()
    # 情感分布
    senti_rows = (await db.execute(
        select(TouristFeedback.sentiment, func.count(TouristFeedback.id))
        .group_by(TouristFeedback.sentiment))).all()
    senti_total = sum(c for _, c in senti_rows) or 1
    sentiment = {s: round(c / senti_total, 3) for s, c in senti_rows}
    for k in ("positive", "neutral", "negative"):
        sentiment.setdefault(k, 0.0)

    # 热门问题 TOP8
    hot_rows = (await db.execute(
        select(TouristFeedback.question, func.count(TouristFeedback.id).label("c"))
        .group_by(TouristFeedback.question)
        .order_by(func.count(TouristFeedback.id).desc()).limit(8))).all()

    # 近7日趋势
    trend = []
    for i in range(6, -1, -1):
        d0 = today - timedelta(days=i)
        d1 = d0 + timedelta(days=1)
        c = (await db.execute(
            select(func.count(TouristFeedback.id))
            .where(TouristFeedback.created_at >= d0)
            .where(TouristFeedback.created_at < d1))).scalar() or 0
        trend.append({"date": d0.strftime("%m-%d"), "count": c})

    # 景点热度(扫码签到统计)
    spot_rows = (await db.execute(
        select(SpotVisit.spot_name, func.count(SpotVisit.id))
        .group_by(SpotVisit.spot_name)
        .order_by(func.count(SpotVisit.id).desc()).limit(8))).all()

    return {
        "today_visitors": today_visitors,
        "today_qa": today_qa,
        "week_qa": week_qa,
        "avg_satisfaction": round(float(avg_sat), 2) if avg_sat else None,
        "sentiment": sentiment,
        "hot_questions": [{"question": q, "count": c} for q, c in hot_rows],
        "trend_7days": trend,
        "spot_heat": [{"name": n, "heat": c} for n, c in spot_rows],
    }


# ---------------- 游客感受度报告 ----------------
@router.get("/tourist-analysis")
async def get_tourist_analysis(db: AsyncSession = Depends(get_db)):
    # 情感趋势(近7日每日情感)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    daily_sentiment = []
    for i in range(6, -1, -1):
        d0 = today - timedelta(days=i)
        d1 = d0 + timedelta(days=1)
        rows = (await db.execute(
            select(TouristFeedback.sentiment, func.count(TouristFeedback.id))
            .where(TouristFeedback.created_at >= d0)
            .where(TouristFeedback.created_at < d1)
            .group_by(TouristFeedback.sentiment))).all()
        item = {"date": d0.strftime("%m-%d"), "positive": 0, "neutral": 0, "negative": 0}
        for s, c in rows:
            if s in item:
                item[s] = c
        daily_sentiment.append(item)

    # 关注点词云(高频问题关键词)
    questions = (await db.execute(select(TouristFeedback.question))).scalars().all()
    keywords = ["灵山大佛", "九龙灌浴", "梵宫", "五印坛城", "拈花湾", "门票",
                "交通", "素斋", "路线", "开放时间", "菩提", "祥符禅寺", "停车", "住宿"]
    cloud = []
    for kw in keywords:
        c = sum(1 for q in questions if kw in q)
        if c:
            cloud.append({"word": kw, "count": c})
    cloud.sort(key=lambda x: -x["count"])

    # 负面反馈样本(供运营改进)
    neg_rows = (await db.execute(
        select(TouristFeedback.question, TouristFeedback.created_at)
        .where(TouristFeedback.sentiment == "negative")
        .order_by(TouristFeedback.id.desc()).limit(10))).all()

    # 满意度分布
    sat_rows = (await db.execute(
        select(TouristFeedback.satisfaction, func.count(TouristFeedback.id))
        .where(TouristFeedback.satisfaction.isnot(None))
        .group_by(TouristFeedback.satisfaction))).all()

    return {
        "daily_sentiment": daily_sentiment,
        "attention_cloud": cloud,
        "negative_samples": [{"question": q, "time": str(t)} for q, t in neg_rows],
        "satisfaction_distribution": {str(s): c for s, c in sat_rows},
    }


# ---------------- 反馈流 ----------------
@router.get("/feedback")
async def get_feedback(page: int = 1, page_size: int = 20,
                       db: AsyncSession = Depends(get_db)):
    q = (select(TouristFeedback)
         .order_by(TouristFeedback.id.desc())
         .offset((page - 1) * page_size).limit(page_size))
    rows = (await db.execute(q)).scalars().all()
    total = (await db.execute(select(func.count(TouristFeedback.id)))).scalar() or 0
    return {
        "items": [{
            "id": r.id,
            "time": r.created_at.strftime("%m-%d %H:%M") if r.created_at else "",
            "tourist": r.tourist_id,
            "content": r.question,
            "sentiment": r.sentiment,
            "satisfaction": r.satisfaction,
        } for r in rows],
        "total": total,
    }


class RateRequest(BaseModel):
    feedback_id: int
    satisfaction: int  # 1-5


@router.post("/rate")
async def rate_answer(req: RateRequest, db: AsyncSession = Depends(get_db)):
    """游客对回答打分(1-5),回填满意度"""
    row = await db.get(TouristFeedback, req.feedback_id)
    if row:
        row.satisfaction = max(1, min(5, req.satisfaction))
        await db.commit()
        return {"ok": True}
    return {"ok": False, "message": "记录不存在"}


@router.post("/suggestions")
async def gen_suggestions(db: AsyncSession = Depends(get_db)):
    """
    AI运营建议:大模型基于真实交互数据(高频问题+负面反馈+情感分布)
    生成可落地的服务改进建议
    """
    # 汇总真实数据
    hot = (await db.execute(
        select(TouristFeedback.question, func.count(TouristFeedback.id).label("c"))
        .group_by(TouristFeedback.question)
        .order_by(func.count(TouristFeedback.id).desc()).limit(10))).all()
    neg = (await db.execute(
        select(TouristFeedback.question)
        .where(TouristFeedback.sentiment == "negative")
        .order_by(TouristFeedback.id.desc()).limit(10))).scalars().all()
    senti = (await db.execute(
        select(TouristFeedback.sentiment, func.count(TouristFeedback.id))
        .group_by(TouristFeedback.sentiment))).all()
    total_qa = (await db.execute(select(func.count(TouristFeedback.id)))).scalar() or 0

    from app.services.llm_service import llm_service
    data_brief = (
        f"总问答量:{total_qa}\n"
        f"高频问题:{[f'{q}({c}次)' for q, c in hot]}\n"
        f"情感分布:{dict(senti)}\n"
        f"负面反馈样本:{list(neg)[:8]}"
    )
    prompt = (
        "你是景区运营分析专家。以下是灵山胜境景区AI数字人导览系统的真实运营数据,"
        "请生成3-5条可落地的运营改进建议。\n" + data_brief +
        "\n要求:每条建议给出 priority(high/medium/low)和具体内容(50字内,具体可执行)。"
        "严格按如下JSON数组格式输出,不要输出其他内容:"
        '[{"priority":"high","content":"..."},...]'
    )
    raw = await llm_service.chat_once(prompt, max_tokens=500, temperature=0.4)
    suggestions = []
    if raw:
        import json as _json, re as _re
        m = _re.search(r"\[.*\]", raw, _re.S)
        if m:
            try:
                arr = _json.loads(m.group(0))
                for it in arr[:5]:
                    if it.get("content"):
                        suggestions.append({
                            "priority": it.get("priority", "medium"),
                            "content": it["content"]})
            except Exception:
                pass
    if not suggestions:  # 降级:规则建议
        suggestions = [
            {"priority": "high", "content": "将高频问题TOP3整理为数字人主动推荐话术,减少重复咨询"},
            {"priority": "medium", "content": "针对负面反馈涉及的场景,补充知识库对应讲解内容"},
            {"priority": "low", "content": "在热门景点增设数字人二维码立牌,引导游客使用AI导览"},
        ]
    return {"suggestions": suggestions, "data": {"total_qa": total_qa}}


class SpotCheckin(BaseModel):
    tourist_id: str = "guest"
    spot_id: str
    spot_name: str
    method: str = "qrcode"


@router.post("/checkin")
async def spot_checkin(req: SpotCheckin, db: AsyncSession = Depends(get_db)):
    """景点扫码签到(GPS弱信号场景的定位替代方案)"""
    db.add(SpotVisit(tourist_id=req.tourist_id, spot_id=req.spot_id,
                     spot_name=req.spot_name, method=req.method))
    await db.commit()
    return {"ok": True, "spot": req.spot_name}


@router.get("/my-visits")
async def my_visits(tourist_id: str, db: AsyncSession = Depends(get_db)):
    """个人足迹:当前游客的扫码签到记录(个人中心展示)"""
    rows = (await db.execute(
        select(SpotVisit).where(SpotVisit.tourist_id == tourist_id)
        .order_by(SpotVisit.id.desc()).limit(20))).scalars().all()
    return {
        "visits": [{
            "spot_id": r.spot_id, "spot_name": r.spot_name,
            "time": r.created_at.strftime("%m-%d %H:%M") if r.created_at else "",
        } for r in rows],
        "total": len(rows),
    }
