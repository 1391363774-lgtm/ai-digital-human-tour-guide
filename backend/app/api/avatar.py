from fastapi import APIRouter

router = APIRouter()


@router.get("/list")
async def list_avatars():
    return {
        "avatars": [
            {
                "id": 1,
                "name": "灵小仙",
                "style": "修仙者",
                "voice": "温柔女声",
                "is_active": True,
                "dialects": ["普通话", "无锡话"],
            },
            {
                "id": 2,
                "name": "灵小仙·禅服版",
                "style": "禅服",
                "voice": "沉稳女声",
                "is_active": False,
                "dialects": ["普通话"],
            },
            {
                "id": 3,
                "name": "灵小仙·现代版",
                "style": "现代",
                "voice": "活泼女声",
                "is_active": False,
                "dialects": ["普通话", "无锡话"],
            },
        ]
    }


@router.get("/config/{avatar_id}")
async def get_avatar_config(avatar_id: int):
    return {
        "id": avatar_id,
        "name": "灵小仙",
        "appearance": {
            "hair": "高髻",
            "clothing": "白金修仙长袍",
            "badge": "金色莲花",
            "color": "#C5A55A",
        },
        "voice": {
            "engine": "CosyVoice",
            "voice_type": "温柔女声",
            "speed": 1.0,
        },
        "expression": {
            "version": "standard",
            "smile_amplitude": 0.7,
            "blink_frequency": 0.3,
        },
        "behavior": {
            "greeting": "阿弥陀佛，欢迎来到灵山胜境",
            "recommend_strategy": "balanced",
            "auto_follow": True,
        },
    }


@router.put("/config/{avatar_id}")
async def update_avatar_config(avatar_id: int):
    return {"message": "配置已更新"}
