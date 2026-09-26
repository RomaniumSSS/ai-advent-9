"""Вычисление планового слота и запуск без скрытого catch-up."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from day18.config import PROFILE, ZONE
from day18.models import Slot


def _at_18(local_date: date) -> datetime:
    zone = ZoneInfo(ZONE)
    wall = datetime.combine(local_date, time(18))
    first = wall.replace(tzinfo=zone, fold=0)
    second = wall.replace(tzinfo=zone, fold=1)
    if first.utcoffset() != second.utcoffset():
        raise ValueError("18:00 в зоне неоднозначно")
    if first.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != wall:
        raise ValueError("18:00 в зоне не существует")
    return first.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def slot_for(local_date: date) -> Slot:
    instant = _at_18(local_date)
    previous = _at_18(local_date - timedelta(days=1))
    return Slot(local_date.isoformat(), _iso(instant), _iso(previous), _iso(instant), ZONE, PROFILE)


def due_now(now: datetime) -> Slot | None:
    if now.tzinfo is None:
        raise ValueError("Требуется timezone-aware time")
    local = now.astimezone(ZoneInfo(ZONE))
    if (local.hour, local.minute) != (18, 0):
        return None
    return slot_for(local.date())
