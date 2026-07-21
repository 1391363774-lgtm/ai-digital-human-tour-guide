from __future__ import annotations

import json
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.visitor_event import VisitorEvent
from app.schemas.behavior import VisitorEventCreate


class VisitorEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: VisitorEventCreate) -> VisitorEvent:
        event = VisitorEvent(**self._to_model_kwargs(payload))
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def bulk_create(self, payloads: list[VisitorEventCreate]) -> list[VisitorEvent]:
        events = [VisitorEvent(**self._to_model_kwargs(payload)) for payload in payloads]
        self.db.add_all(events)
        self.db.commit()
        for event in events:
            self.db.refresh(event)
        return events

    def list(self, limit: int = 100, offset: int = 0) -> list[VisitorEvent]:
        statement = select(VisitorEvent).order_by(VisitorEvent.occurred_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(statement).all())

    def stats(self, limit: int = 5000) -> dict:
        events = self.list(limit=limit, offset=0)
        event_type_counts = Counter(event.event_type for event in events)
        source_counts = Counter(event.source or "unknown" for event in events)
        top_spot_counts = Counter(str(event.spot_id) for event in events if event.spot_id is not None)
        durations = [event.duration_seconds for event in events if event.duration_seconds is not None]
        average_duration = round(sum(durations) / len(durations), 2) if durations else 0
        return {
            "total": len(events),
            "event_type_counts": dict(event_type_counts),
            "source_counts": dict(source_counts),
            "top_spot_counts": dict(top_spot_counts.most_common(10)),
            "average_duration_seconds": average_duration,
        }

    def _to_model_kwargs(self, payload: VisitorEventCreate) -> dict:
        kwargs = {
            "user_id": payload.user_id,
            "session_id": payload.session_id,
            "event_type": payload.event_type,
            "target_type": payload.target_type,
            "target_id": payload.target_id,
            "spot_id": payload.spot_id,
            "page_path": payload.page_path,
            "source": payload.source,
            "duration_seconds": payload.duration_seconds,
            "metadata_json": json.dumps(payload.metadata, ensure_ascii=False) if payload.metadata else None,
        }
        if payload.occurred_at is not None:
            kwargs["occurred_at"] = payload.occurred_at
        return kwargs


def visitor_event_to_dict(event: VisitorEvent) -> dict:
    metadata = None
    if event.metadata_json:
        try:
            metadata = json.loads(event.metadata_json)
        except json.JSONDecodeError:
            metadata = {"raw": event.metadata_json}
    return {
        "id": event.id,
        "user_id": event.user_id,
        "session_id": event.session_id,
        "event_type": event.event_type,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "spot_id": event.spot_id,
        "page_path": event.page_path,
        "source": event.source,
        "duration_seconds": event.duration_seconds,
        "metadata": metadata,
        "occurred_at": event.occurred_at,
        "created_at": event.created_at,
    }
