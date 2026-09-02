from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class MultimodalAnswer:
    answer: str
    provider: str
    model: str
    configured: bool
    error: str | None = None


class MultimodalGuideService:
    def analyze_image(self, image_bytes: bytes, mime_type: str, question: str) -> MultimodalAnswer:
        settings = get_settings()
        provider = settings.multimodal_provider
        model = settings.multimodal_model

        if not settings.qwen_api_key:
            return MultimodalAnswer(
                answer=(
                    "已接收图片，但当前未配置 QWEN_API_KEY，无法真正调用 Qwen-VL 多模态大模型。"
                    "请在后端环境变量中配置 QWEN_API_KEY 后重启服务；配置后该入口会使用"
                    f" {model} 对景区图片和文字问题进行联合理解。"
                ),
                provider=provider,
                model=model,
                configured=False,
            )

        image_data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        prompt = question.strip() or "请识别图片中的景区元素，并用导游口吻说明它可能对应的景点、文化含义和游览建议。"
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是灵山胜境 AI 数字人导游。请结合图片和游客问题回答。"
                        "只做景区导览、景点识别、文化讲解和路线建议；不确定时要说明不确定，不能编造。"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                        {"type": "text", "text": prompt},
                    ],
                },
            ],
            "temperature": 0.2,
            "max_tokens": 500,
        }
        base_url = (settings.qwen_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
        request = urllib.request.Request(
            url=f"{base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.qwen_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            answer = data["choices"][0]["message"]["content"]
        except (urllib.error.URLError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            answer = f"多模态模型调用失败：{exc}。请检查 QWEN_API_KEY、网络和模型权限。"
            return MultimodalAnswer(answer=answer, provider=provider, model=model, configured=bool(settings.qwen_api_key), error=str(exc))

        return MultimodalAnswer(answer=answer, provider=provider, model=model, configured=True)


def get_multimodal_capability() -> dict:
    settings = get_settings()
    return {
        "provider": settings.multimodal_provider,
        "model": settings.multimodal_model,
        "configured": bool(settings.qwen_api_key),
        "input_modes": ["image", "text"],
        "purpose": "景区图片识别、图文联合问答、文化讲解和路线建议",
    }
