from __future__ import annotations

from collections import Counter
from pathlib import Path

from sqlalchemy import JSON, String, func, select
from sqlalchemy.orm import Mapped, mapped_column

from autoshelf.db import Base, Database
from autoshelf.paths import global_db_path


class EventRecord(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


def record_event(
    event_type: str, payload: dict[str, object] | None = None, db_path: Path | None = None
) -> None:
    database = Database(db_path or global_db_path())
    with database.session() as session:
        session.add(EventRecord(event_type=event_type, payload=payload or {}))


def collect_stats(db_path: Path | None = None) -> dict[str, object]:
    database = Database(db_path or global_db_path())
    database.initialize()
    with database.session() as session:
        counts = dict(
            session.execute(
                select(EventRecord.event_type, func.count()).group_by(EventRecord.event_type)
            ).all()
        )
        token_totals = Counter()
        for payload in session.scalars(select(EventRecord.payload)).all():
            for key in (
                "input_tokens",
                "output_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
            ):
                if isinstance(payload.get(key), int):
                    token_totals[key] += int(payload[key])
        return {
            "events": counts,
            "tokens": dict(token_totals),
        }
