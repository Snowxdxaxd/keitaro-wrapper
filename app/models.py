"""Модель БД обёртки: журнал действий над кампаниями."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CampaignAction(Base):
    """История: что обёртка сделала в Keitaro (создание/добавление/удаление)."""

    __tablename__ = "campaign_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    action: Mapped[str] = mapped_column(String(32))  # create | add_offer | remove_offer
    campaign_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    campaign_name: Mapped[str] = mapped_column(String(255), default="")
    details: Mapped[str] = mapped_column(Text, default="")  # JSON с деталями
