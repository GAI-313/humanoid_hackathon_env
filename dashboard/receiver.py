"""イベント受信サーバー（FastAPI）。POST /events を検証して logs/events.jsonl に追記する。

起動: pixi run receiver   （単体）／ pixi run dashboard （Streamlit と同時）
仕様: docs/log_schema.md
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, field_validator

from common import LOG_PATH, append_event, read_events

app = FastAPI(title="pick-r1 receiver")


class EventIn(BaseModel):
    """送信側が POST する本文。id / received_at は付けない（receiver が付与）。"""

    model_config = ConfigDict(extra="forbid")

    v: int
    ts: str
    robot: str
    run_id: str
    box_id: Optional[str]  # 必須キー。QR 未読なら null
    event: str
    zone: Optional[str]  # 必須キー。不明なら null
    source: Literal["recognition", "control", "dashboard"]
    detail: Optional[str] = None
    error: Optional[dict[str, Any]] = None
    data: Optional[dict[str, Any]] = None

    @field_validator("ts")
    @classmethod
    def _ts_has_timezone(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value)  # 不正なら ValueError → 422
        if parsed.tzinfo is None:
            raise ValueError("ts にはタイムゾーンが必要です（例 +09:00）")
        return value


@app.post("/events", status_code=201)
def post_event(body: EventIn) -> dict:
    fields = body.model_dump()
    for key in ("detail", "error", "data"):  # 任意項目は無ければ省略
        if fields[key] is None:
            del fields[key]
    event = {
        "v": fields.pop("v"),
        "id": uuid.uuid4().hex,
        "ts": fields.pop("ts"),
        "received_at": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        **fields,
    }
    append_event(event)
    return {"id": event["id"]}


@app.get("/health")
def health() -> dict:
    events = read_events()
    return {
        "ok": True,
        "log": str(LOG_PATH),
        "count": len(events),
        "last_received_at": events[-1].get("received_at") if events else None,
    }
