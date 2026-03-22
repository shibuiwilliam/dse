from __future__ import annotations

from datetime import UTC, datetime, timedelta

from dse.intelligence.prospective import (
    RecurrenceType,
    compute_fire_patch,
    compute_next_trigger_at,
    evaluate_time_trigger,
    should_fire,
)


class TestTimeTrigger:
    def test_fires_when_past(self) -> None:
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        assert evaluate_time_trigger(past) is True

    def test_not_fires_when_future(self) -> None:
        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        assert evaluate_time_trigger(future) is False

    def test_empty_trigger_at(self) -> None:
        assert evaluate_time_trigger(None) is False
        assert evaluate_time_trigger("") is False


class TestShouldFire:
    def test_time_trigger_past(self) -> None:
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        assert should_fire({"trigger_type": "time", "trigger_at": past}) is True

    def test_event_trigger_always_false(self) -> None:
        assert should_fire({"trigger_type": "event", "trigger_event": "test"}) is False

    def test_condition_trigger_returns_false(self) -> None:
        assert should_fire({"trigger_type": "condition", "trigger_condition": "x > 5"}) is False


class TestRecurrence:
    def test_daily_adds_one_day(self) -> None:
        now = datetime(2026, 3, 20, 10, 0, tzinfo=UTC)
        next_at = compute_next_trigger_at(now, RecurrenceType.DAILY)
        assert next_at == datetime(2026, 3, 21, 10, 0, tzinfo=UTC)

    def test_weekly_adds_seven_days(self) -> None:
        now = datetime(2026, 3, 20, 10, 0, tzinfo=UTC)
        next_at = compute_next_trigger_at(now, RecurrenceType.WEEKLY)
        assert next_at == datetime(2026, 3, 27, 10, 0, tzinfo=UTC)

    def test_once_returns_same(self) -> None:
        now = datetime(2026, 3, 20, 10, 0, tzinfo=UTC)
        next_at = compute_next_trigger_at(now, RecurrenceType.ONCE)
        assert next_at == now


class TestFirePatch:
    def test_once_trigger_sets_triggered_true(self) -> None:
        record = {
            "trigger_type": "time",
            "trigger_at": "2026-03-19T10:00:00+00:00",
            "recurrence": "once",
        }
        patch = compute_fire_patch(record)
        assert patch["is_triggered"] is True
        assert "triggered_at" in patch

    def test_daily_recurrence_resets_trigger(self) -> None:
        record = {
            "trigger_type": "time",
            "trigger_at": "2026-03-20T10:00:00+00:00",
            "recurrence": "daily",
        }
        patch = compute_fire_patch(record)
        assert patch["is_triggered"] is False  # Reset for next occurrence
        assert "trigger_at" in patch
        new_at = datetime.fromisoformat(str(patch["trigger_at"]))
        assert new_at.day == 21  # Next day

    def test_event_trigger_no_reschedule(self) -> None:
        record = {"trigger_type": "event", "recurrence": "once"}
        patch = compute_fire_patch(record)
        assert patch["is_triggered"] is True
        assert "trigger_at" not in patch or patch.get("trigger_at") is None
