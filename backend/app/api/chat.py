from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.chat_service import chat_service

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[int] = None
    dialect: str = "mandarin"  # mandarin / wuxi


class ChatResponse(BaseModel):
    answer: str
    intent: str
    sources: list


@router.post("/send", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    result = await chat_service.chat(request.message, request.session_id, request.dialect)
    return result


@router.get("/intent")
async def get_intents():
    return {
        "intents": [
            "scenic_spot", "route", "ticket", "time",
            "traffic", "food", "hotel", "general",
        ]
    }


@router.get("/quick-questions")
async def get_quick_questions():
    return {
        "questions": [
            "灵山大佛有多高？",
            "九龙灌浴几点开始表演？",
            "推荐一条4小时亲子路线",
            "灵山梵宫有什么特别之处？",
            "拈花湾的禅行灯光秀是什么时候？",
            "门票多少钱？怎么预约？",
        ]
    }
