from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, JSON, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class MatchHistory(Base):
    """The v1 normalized match record and lossless parser payload."""

    __tablename__ = "match_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    my_deck: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON)
    opponent_deck: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON)
    opponent_colors: Mapped[list[Any]] = mapped_column(JSON)
    match_result: Mapped[str] = mapped_column(String(32))
    event_id: Mapped[str] = mapped_column(String(128), index=True)
    on_play: Mapped[bool] = mapped_column(nullable=False)
    opponent_platform: Mapped[str] = mapped_column(String(64))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
