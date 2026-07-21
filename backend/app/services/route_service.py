from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.recommendation import Recommendation, RecommendationItem
from app.models.scenic import ScenicSpot
from app.repositories.scenic_repository import ScenicSpotRepository

SPOT_DURATION_MINUTES = {
    "灵山胜境": 240,
    "灵山大佛": 60,
    "祥符禅寺": 40,
    "九龙灌浴": 25,
    "灵山梵宫": 75,
    "五印坛城": 50,
    "佛教文化博览馆": 45,
    "百子戏弥勒": 15,
    "佛足坛": 15,
    "菩提大道": 20,
    "阿育王柱": 15,
    "灵山大照壁": 10,
    "五明桥": 10,
    "五智门": 15,
    "降魔成道": 15,
    "拈花湾禅意小镇": 240,
    "拈花广场": 20,
    "拈花塔": 25,
    "香月花街": 60,
    "拈花堂": 50,
    "五灯湖": 45,
    "梵天花海": 45,
    "妙音台": 35,
    "微笑广场": 20,
}


@dataclass(frozen=True)
class RouteSpot:
    spot: ScenicSpot
    stay_minutes: int
    explanation: str


@dataclass(frozen=True)
class RouteRecommendationResult:
    recommendation_id: int | None
    interest: str
    duration_hours: int
    group_type: str
    reason: str
    spots: list[RouteSpot]


class RouteRecommendationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.spot_repository = ScenicSpotRepository(db)

    def recommend(
        self,
        interest: str,
        duration_hours: int,
        group_type: str,
        persist: bool = True,
    ) -> RouteRecommendationResult:
        spots = self.spot_repository.list_all()
        if not spots:
            return RouteRecommendationResult(
                recommendation_id=None,
                interest=interest,
                duration_hours=duration_hours,
                group_type=group_type,
                reason="当前景点库为空，请先导入官方灵山胜境结构化数据。",
                spots=[],
            )

        target_minutes = duration_hours * 60
        scored = sorted(
            ((score_spot(spot, interest, group_type), spot) for spot in spots),
            key=lambda item: item[0],
            reverse=True,
        )
        selected: list[RouteSpot] = []
        used_minutes = 0
        for score, spot in scored:
            if score <= 0 and selected:
                continue
            stay_minutes = estimate_stay_minutes(spot, group_type)
            if used_minutes + stay_minutes > target_minutes and selected:
                continue
            selected.append(
                RouteSpot(
                    spot=spot,
                    stay_minutes=stay_minutes,
                    explanation=build_explanation(spot, interest, group_type),
                )
            )
            used_minutes += stay_minutes
            if used_minutes >= target_minutes * 0.8:
                break

        if not selected:
            selected = [
                RouteSpot(
                    spot=spot,
                    stay_minutes=estimate_stay_minutes(spot, group_type),
                    explanation=build_explanation(spot, interest, group_type),
                )
                for _, spot in scored[:3]
            ]

        reason = build_route_reason(interest, duration_hours, group_type, selected)
        recommendation_id = self._persist(interest, duration_hours, group_type, reason, selected) if persist else None
        return RouteRecommendationResult(
            recommendation_id=recommendation_id,
            interest=interest,
            duration_hours=duration_hours,
            group_type=group_type,
            reason=reason,
            spots=selected,
        )

    def _persist(
        self,
        interest: str,
        duration_hours: int,
        group_type: str,
        reason: str,
        selected: list[RouteSpot],
    ) -> int:
        recommendation = Recommendation(
            interest=interest,
            duration_hours=duration_hours,
            group_type=group_type,
            reason=reason,
        )
        self.db.add(recommendation)
        self.db.flush()
        for order, item in enumerate(selected, start=1):
            self.db.add(
                RecommendationItem(
                    recommendation_id=recommendation.id,
                    spot_id=item.spot.id,
                    sort_order=order,
                    stay_minutes=item.stay_minutes,
                    explanation=item.explanation,
                )
            )
        self.db.commit()
        self.db.refresh(recommendation)
        return recommendation.id


def score_spot(spot: ScenicSpot, interest: str, group_type: str) -> int:
    text = " ".join(
        item or ""
        for item in [
            spot.name,
            spot.category,
            spot.core_function,
            spot.cultural_meaning,
            spot.description,
            spot.highlights,
        ]
    )
    score = 0
    keyword_groups = build_interest_keywords(interest, group_type)
    for weight, keywords in keyword_groups:
        score += weight * sum(1 for keyword in keywords if keyword in text)
    return score


def build_interest_keywords(interest: str, group_type: str) -> list[tuple[int, list[str]]]:
    text = f"{interest} {group_type}"
    groups: list[tuple[int, list[str]]] = []
    if any(keyword in text for keyword in ("历史", "文化", "佛", "禅", "祈福")):
        groups.append((3, ["历史", "文化", "佛", "禅", "祈福", "朝圣", "圣坛", "大佛"]))
    if any(keyword in text for keyword in ("自然", "风光", "拍照", "打卡")):
        groups.append((3, ["景观", "广场", "大道", "湖", "花", "塔", "打卡"]))
    if any(keyword in text for keyword in ("亲子", "家庭", "孩子", "老人")):
        groups.append((3, ["互动", "表演", "体验", "广场", "休闲", "便利"]))
    if any(keyword in text for keyword in ("轻松", "休闲", "慢游")):
        groups.append((2, ["休闲", "小镇", "商业", "体验", "漫步"]))
    groups.append((1, [interest]))
    return groups


def estimate_stay_minutes(spot: ScenicSpot, group_type: str) -> int:
    if spot.recommended_duration_minutes:
        return spot.recommended_duration_minutes
    if spot.name in SPOT_DURATION_MINUTES:
        base = SPOT_DURATION_MINUTES[spot.name]
    else:
        text = f"{spot.name} {spot.category} {spot.core_function or ''} {spot.open_info or ''}"
        if "每场时长约15分钟" in text:
            base = 25
        elif "每场时长约20分钟" in text:
            base = 35
        elif "每场时长约30分钟" in text:
            base = 45
        elif "每场时长约40分钟" in text:
            base = 50
        elif "小镇" in text:
            base = 180
        elif "博览馆" in text or "展厅" in text or "艺术" in text:
            base = 45
        elif "演艺" in text or "表演" in text or "动态" in text:
            base = 30
        elif "寺" in text or "佛" in text or "坛城" in text:
            base = 40
        elif "广场" in text or "大道" in text or "桥" in text or "壁" in text:
            base = 15
        else:
            base = 25
    if any(keyword in group_type for keyword in ("亲子", "老人", "家庭")):
        base += 10
    return base


def build_explanation(spot: ScenicSpot, interest: str, group_type: str) -> str:
    reason_parts = [f"契合“{interest}”偏好"]
    if spot.category:
        reason_parts.append(f"属于{spot.category}")
    if group_type:
        reason_parts.append(f"适合{group_type}")
    return "，".join(reason_parts) + "。"


def build_route_reason(
    interest: str,
    duration_hours: int,
    group_type: str,
    selected: list[RouteSpot],
) -> str:
    names = "、".join(item.spot.name for item in selected[:4])
    return (
        f"这条路线按“{interest}”偏好和约 {duration_hours} 小时游玩时长生成，"
        f"兼顾{group_type}的节奏，优先安排 {names} 等景点。"
    )
