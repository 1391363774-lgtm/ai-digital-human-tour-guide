from pydantic import BaseModel


class DashboardMetric(BaseModel):
    label: str
    value: int | float
    unit: str | None = None


class DashboardOverviewOut(BaseModel):
    metrics: list[DashboardMetric]
    event_type_counts: dict[str, int]
    feedback_sentiment_counts: dict[str, int]
    favorite_type_counts: dict[str, int]
    knowledge_status_counts: dict[str, int]
    top_spot_counts: dict[str, int]
    average_rating: float
    average_satisfaction: float
    average_latency_ms: float
    average_duration_seconds: float
    today_visitors: int = 0
    week_visitors: int = 0
    questions_trend: list[dict[str, int | str]] = []
    top_questions: list[dict[str, int | str]] = []
    daily_satisfaction: list[dict[str, int | float | str]] = []
    word_cloud: list[dict[str, int | str]] = []
