from fastapi import APIRouter

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard():
    return {
        "today_visits": 1286,
        "week_visits": 8452,
        "avg_satisfaction": 3.72,
        "online_avatars": 3,
        "trend_7days": [980, 1120, 1050, 1286, 1190, 1340, 1286],
        "hot_questions": [
            {"question": "灵山大佛有多高？", "count": 328},
            {"question": "九龙灌浴表演时间", "count": 286},
            {"question": "推荐亲子路线", "count": 245},
        ],
        "spot_heat": [
            {"name": "灵山大佛", "heat": 95},
            {"name": "九龙灌浴", "heat": 88},
            {"name": "灵山梵宫", "heat": 82},
            {"name": "五印坛城", "heat": 65},
            {"name": "祥符禅寺", "heat": 58},
            {"name": "菩提大道", "heat": 45},
        ],
        "sentiment": {"positive": 0.628, "neutral": 0.282, "negative": 0.09},
    }


@router.get("/tourist-analysis")
async def get_tourist_analysis():
    return {
        "age_distribution": {
            "19-25": "12%",
            "26-35": "35%",
            "36-45": "28%",
            "46-55": "18%",
            "56-71": "7%",
        },
        "avg_age": 37.8,
        "avg_ticket_cost": 99.73,
        "avg_total_cost": 1234.56,
        "satisfaction_distribution": {
            "2分": 948,
            "3分": 8106,
            "4分": 6501,
            "5分": 4446,
        },
        "attention_cloud": [
            "灵山大佛", "九龙灌浴", "梵宫", "五印坛城",
            "菩提大道", "百子戏弥勒", "拈花湾", "门票",
            "交通", "素斋",
        ],
        "suggestions": [
            {"priority": "high", "content": "优化交通指引信息，减少入园咨询量"},
            {"priority": "medium", "content": "增加九龙灌浴表演倒计时提醒功能"},
            {"priority": "medium", "content": "针对核心客群(26-45岁)深化文化讲解内容"},
        ],
    }


@router.get("/feedback")
async def get_feedback(page: int = 1, page_size: int = 20):
    return {
        "items": [
            {
                "id": 1,
                "time": "14:32",
                "tourist": "U10001",
                "content": "灵山大佛有多高？",
                "sentiment": "positive",
                "satisfaction": 5,
                "status": "processed",
            },
            {
                "id": 2,
                "time": "14:28",
                "tourist": "U10002",
                "content": "推荐亲子路线",
                "sentiment": "positive",
                "satisfaction": 5,
                "status": "processed",
            },
            {
                "id": 3,
                "time": "14:25",
                "tourist": "U10003",
                "content": "九龙灌浴几点？",
                "sentiment": "neutral",
                "satisfaction": 4,
                "status": "processed",
            },
            {
                "id": 4,
                "time": "14:20",
                "tourist": "U10004",
                "content": "等太久",
                "sentiment": "negative",
                "satisfaction": 2,
                "status": "pending",
            },
        ],
        "total": 4,
    }
