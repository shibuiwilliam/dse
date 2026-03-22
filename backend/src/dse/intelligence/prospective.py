from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum

import structlog

logger = structlog.get_logger(__name__)


class RecurrenceType(StrEnum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"


def evaluate_time_trigger(trigger_at_str: str | None) -> bool:
    """Check if a TIME trigger should fire (trigger_at is in the past)."""
    if not trigger_at_str:
        return False
    trigger_at = datetime.fromisoformat(trigger_at_str)
    return datetime.now(UTC) >= trigger_at


def compute_next_trigger_at(current: datetime, recurrence: str) -> datetime:
    """Compute the next trigger time for recurring prospective memories."""
    if recurrence == RecurrenceType.DAILY:
        return current + timedelta(days=1)
    if recurrence == RecurrenceType.WEEKLY:
        return current + timedelta(weeks=1)
    return current


def should_fire(record: dict[str, object]) -> bool:
    """Evaluate whether a prospective memory should fire.

    TIME triggers fire when trigger_at is in the past.
    EVENT triggers only fire via external notification (returns False here).
    CONDITION triggers require LLM evaluation (returns False here — handled separately).
    """
    trigger_type = record.get("trigger_type")
    if trigger_type == "time":
        return evaluate_time_trigger(str(record.get("trigger_at", "")))
    return False


def compute_fire_patch(record: dict[str, object]) -> dict[str, object]:
    """Compute the patch dict for firing a prospective memory."""
    patch: dict[str, object] = {
        "is_triggered": True,
        "triggered_at": datetime.now(UTC).isoformat(),
    }

    recurrence = str(record.get("recurrence", "once"))
    if recurrence != RecurrenceType.ONCE and record.get("trigger_type") == "time":
        trigger_at_str = str(record.get("trigger_at", ""))
        if trigger_at_str:
            current = datetime.fromisoformat(trigger_at_str)
            next_at = compute_next_trigger_at(current, recurrence)
            patch["trigger_at"] = next_at.isoformat()
            patch["is_triggered"] = False  # Reset for next occurrence

    return patch
