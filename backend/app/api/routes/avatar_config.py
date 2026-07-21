from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from app.schemas.response import success

router = APIRouter(prefix="/api/admin/avatar", tags=["avatar-config"])

PROJECT_ROOT = Path(__file__).resolve().parents[4]
AVATAR_CONFIG_PATH = PROJECT_ROOT / "frontend" / "public" / "avatar-config.json"
LIVE2D_MODELS_PATH = PROJECT_ROOT / "frontend" / "public" / "models"


@router.get("/config")
def get_avatar_config():
    if not AVATAR_CONFIG_PATH.exists():
        raise HTTPException(status_code=404, detail="数字人配置文件不存在")
    try:
        data = json.loads(AVATAR_CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"数字人配置文件格式错误：{exc}") from exc
    return success(data)


@router.get("/models")
def list_live2d_models():
    if not LIVE2D_MODELS_PATH.exists():
        return success([])
    models: list[dict[str, str]] = []
    for model_file in sorted(LIVE2D_MODELS_PATH.glob("*/*.model3.json")):
        folder = model_file.parent.name
        models.append(
            {
                "name": folder,
                "label": model_file.stem.replace(".model3", ""),
                "url": f"/models/{folder}/{model_file.name}",
            }
        )
    return success(models)


@router.put("/config")
def update_avatar_config(payload: dict[str, Any]):
    AVATAR_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    AVATAR_CONFIG_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return success(payload)
