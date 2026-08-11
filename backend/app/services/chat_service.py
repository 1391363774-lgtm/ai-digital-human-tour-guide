from typing import Optional
from app.core.config import settings
import httpx
import json
import asyncio


class ChatService:
    """RAG对话服务 - 检索增强生成"""

    def __init__(self):
        self.llm_api_key = settings.LLM_API_KEY
        self.llm_base_url = settings.LLM_BASE_URL
        self.llm_model = settings.LLM_MODEL

    async def retrieve_knowledge(self, query: str, top_k: int = 5):
        """从向量数据库检索相关知识"""
        # TODO: 接入Milvus向量检索
        # 临时返回示例
        return [
            {"content": "灵山大佛是世界最高露天青铜释迦牟尼立像，通高88米", "score": 0.95, "source": "LS-011"},
            {"content": "九龙灌浴再现释迦牟尼诞生场景，每日4-5场表演", "score": 0.88, "source": "LS-006"},
        ]

    def build_rag_prompt(self, query: str, context: list) -> str:
        """构建RAG提示词"""
        context_text = "\n".join([f"[{i+1}] {c['content']}" for i, c in enumerate(context)])
        return f"""你是灵山胜境的AI数字人导游"灵小仙"，修仙者风格，语气温柔祥和。
请基于以下知识库内容回答游客的问题。如果知识库中没有相关信息，请如实告知。

【知识库内容】
{context_text}

【游客问题】
{query}

【回答要求】
1. 回答准确、简洁、有温度
2. 如果涉及具体景点，请说明位置和推荐游览时间
3. 适当使用佛教文化相关的表达方式
4. 回答控制在200字以内"""

    async def chat(self, query: str, session_id: Optional[int] = None, dialect: str = "mandarin") -> dict:
        """处理用户对话"""
        # 1. 检索知识
        knowledge = await self.retrieve_knowledge(query)
        # 2. 构建Prompt
        prompt = self.build_rag_prompt(query, knowledge)
        # 3. 调用LLM
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.llm_base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.llm_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.llm_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": 500,
                    },
                )
                result = response.json()
                answer = result["choices"][0]["message"]["content"]
        except Exception as e:
            answer = f"抱歉，灵小仙暂时无法回答您的问题。请稍后再试。"

        # 4. 意图识别（简化版）
        intent = self.detect_intent(query)

        return {"answer": answer, "intent": intent, "sources": [k.get("source") for k in knowledge]}

    def detect_intent(self, query: str) -> str:
        """意图识别"""
        intents = {
            "scenic_spot": ["景点", "大佛", "梵宫", "九龙", "菩提", "坛城"],
            "route": ["路线", "推荐", "怎么玩", "安排", "计划"],
            "ticket": ["门票", "价格", "多少钱", "票价"],
            "time": ["开放", "时间", "几点", "表演"],
            "traffic": ["交通", "怎么去", "路线", "公交", "地铁"],
            "food": ["吃饭", "餐厅", "素斋", "美食"],
            "hotel": ["住宿", "酒店", "住"],
        }
        for intent_key, keywords in intents.items():
            if any(kw in query for kw in keywords):
                return intent_key
        return "general"

    async def text_to_speech(self, text: str) -> str:
        """文本转语音"""
        # TODO: 接入CosyVoice TTS
        return ""  # 返回音频URL


chat_service = ChatService()
