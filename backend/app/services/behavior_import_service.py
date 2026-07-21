from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any

from app.schemas.behavior import VisitorEventCreate


HEADER_ALIASES = {
    "user_id": {"user_id", "用户id", "用户ID"},
    "session_id": {"session_id", "会话id", "会话ID", "session"},
    "event_type": {"event_type", "事件类型", "行为类型", "type"},
    "target_type": {"target_type", "对象类型", "目标类型"},
    "target_id": {"target_id", "对象id", "对象ID", "目标id", "目标ID"},
    "spot_id": {"spot_id", "景点id", "景点ID"},
    "page_path": {"page_path", "页面", "页面路径", "path"},
    "source": {"source", "来源", "渠道"},
    "duration_seconds": {"duration_seconds", "停留秒数", "时长", "duration"},
    "occurred_at": {"occurred_at", "发生时间", "时间", "created_at"},
    "metadata": {"metadata", "扩展信息", "备注"},
}


class BehaviorImportError(ValueError):
    pass


class BehaviorImportService:
    def parse_csv(self, raw_bytes: bytes, max_rows: int = 5000) -> tuple[list[VisitorEventCreate], list[str]]:
        text = raw_bytes.decode("utf-8-sig", errors="ignore")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise BehaviorImportError("CSV 缺少表头")

        payloads: list[VisitorEventCreate] = []
        errors: list[str] = []
        for row_number, row in enumerate(reader, start=2):
            if len(payloads) >= max_rows:
                errors.append(f"超过最大导入行数 {max_rows}，后续行已跳过")
                break
            try:
                payloads.append(self.parse_row(row))
            except (ValueError, TypeError) as exc:
                errors.append(f"第 {row_number} 行跳过：{exc}")
        return payloads, errors

    def parse_row(self, row: dict[str, Any]) -> VisitorEventCreate:
        normalized = {self._canonical_key(key): value for key, value in row.items() if key}
        event_type = self._string(normalized.get("event_type"))
        if not event_type:
            raise ValueError("缺少事件类型 event_type")

        return VisitorEventCreate(
            user_id=self._int(normalized.get("user_id")),
            session_id=self._string(normalized.get("session_id")),
            event_type=event_type,
            target_type=self._string(normalized.get("target_type")),
            target_id=self._int(normalized.get("target_id")),
            spot_id=self._int(normalized.get("spot_id")),
            page_path=self._string(normalized.get("page_path")),
            source=self._string(normalized.get("source")) or "import",
            duration_seconds=self._int(normalized.get("duration_seconds")),
            occurred_at=self._datetime(normalized.get("occurred_at")),
            metadata=self._metadata(normalized.get("metadata")),
        )

    def _canonical_key(self, key: str) -> str:
        key = key.strip()
        for canonical, aliases in HEADER_ALIASES.items():
            if key in aliases:
                return canonical
        return key

    def _string(self, value: Any) -> str | None:
        text = str(value).strip() if value is not None else ""
        return text or None

    def _int(self, value: Any) -> int | None:
        text = self._string(value)
        if text is None:
            return None
        return int(float(text))

    def _datetime(self, value: Any) -> datetime | None:
        text = self._string(value)
        if text is None:
            return None
        normalized = text.replace("/", "-").replace("T", " ")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(normalized, fmt)
            except ValueError:
                continue
        return datetime.fromisoformat(text)

    def _metadata(self, value: Any) -> dict[str, Any] | None:
        text = self._string(value)
        if text is None:
            return None
        try:
            loaded = json.loads(text)
            return loaded if isinstance(loaded, dict) else {"value": loaded}
        except json.JSONDecodeError:
            return {"note": text}
