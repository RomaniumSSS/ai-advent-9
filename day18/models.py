"""Типы на границах расписания, модели, MCP и доставки."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Slot:
    local_date: str
    instant_utc: str
    period_start_utc: str
    period_end_utc: str
    timezone: str = "Europe/Warsaw"
    profile: str = "habr_ai_agents_ru_v1"


@dataclass(frozen=True)
class RunContext:
    run_id: str
    slot: Slot
    idempotency_key: str
    origin: str
    no_send: bool

    def tool_arguments(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "scheduled_slot": self.slot.local_date,
            "period_start_utc": self.slot.period_start_utc,
            "period_end_utc": self.slot.period_end_utc,
            "timezone": self.slot.timezone,
            "source_profile_id": self.slot.profile,
            "idempotency_key": self.idempotency_key,
        }


@dataclass(frozen=True)
class ToolProposal:
    ordinal: int
    call_id: str
    raw_call_id: str | None
    name: str
    arguments: object
    valid_id: bool


@dataclass(frozen=True)
class LinkedResult:
    call_id: str
    ordinal: int
    result: dict


@dataclass(frozen=True)
class DeliveryOutcome:
    kind: str  # receipt, pre_send, definitive_rejection, unknown
    message_id: int | None = None
    safe_reason: str = "none"
