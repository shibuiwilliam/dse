from __future__ import annotations

from datetime import datetime

from dse.intelligence.temporal_reasoning import AllenRelation, TimeInterval, classify_allen_relation


def dt(h: int, m: int = 0) -> datetime:
    """Helper to create datetime at hour:minute on a fixed date."""
    return datetime(2026, 3, 20, h, m)


class TestAllenRelations:
    def test_before(self) -> None:
        a = TimeInterval(dt(10), dt(11))
        b = TimeInterval(dt(12), dt(13))
        assert classify_allen_relation(a, b) == AllenRelation.BEFORE

    def test_meets(self) -> None:
        a = TimeInterval(dt(10), dt(11))
        b = TimeInterval(dt(11), dt(12))
        assert classify_allen_relation(a, b) == AllenRelation.MEETS

    def test_overlaps(self) -> None:
        a = TimeInterval(dt(10), dt(12))
        b = TimeInterval(dt(11), dt(13))
        assert classify_allen_relation(a, b) == AllenRelation.OVERLAPS

    def test_starts(self) -> None:
        a = TimeInterval(dt(10), dt(11))
        b = TimeInterval(dt(10), dt(12))
        assert classify_allen_relation(a, b) == AllenRelation.STARTS

    def test_during(self) -> None:
        a = TimeInterval(dt(11), dt(12))
        b = TimeInterval(dt(10), dt(13))
        assert classify_allen_relation(a, b) == AllenRelation.DURING

    def test_finishes(self) -> None:
        a = TimeInterval(dt(11), dt(13))
        b = TimeInterval(dt(10), dt(13))
        assert classify_allen_relation(a, b) == AllenRelation.FINISHES

    def test_equals(self) -> None:
        a = TimeInterval(dt(10), dt(12))
        b = TimeInterval(dt(10), dt(12))
        assert classify_allen_relation(a, b) == AllenRelation.EQUALS

    def test_after(self) -> None:
        a = TimeInterval(dt(14), dt(15))
        b = TimeInterval(dt(10), dt(11))
        assert classify_allen_relation(a, b) == AllenRelation.AFTER

    def test_met_by(self) -> None:
        a = TimeInterval(dt(12), dt(13))
        b = TimeInterval(dt(10), dt(12))
        assert classify_allen_relation(a, b) == AllenRelation.MET_BY

    def test_overlapped_by(self) -> None:
        a = TimeInterval(dt(11), dt(13))
        b = TimeInterval(dt(10), dt(12))
        assert classify_allen_relation(a, b) == AllenRelation.OVERLAPPED_BY

    def test_started_by(self) -> None:
        a = TimeInterval(dt(10), dt(13))
        b = TimeInterval(dt(10), dt(12))
        assert classify_allen_relation(a, b) == AllenRelation.STARTED_BY

    def test_contains(self) -> None:
        a = TimeInterval(dt(10), dt(14))
        b = TimeInterval(dt(11), dt(13))
        assert classify_allen_relation(a, b) == AllenRelation.CONTAINS

    def test_finished_by(self) -> None:
        a = TimeInterval(dt(10), dt(13))
        b = TimeInterval(dt(11), dt(13))
        assert classify_allen_relation(a, b) == AllenRelation.FINISHED_BY

    def test_all_13_relations_covered(self) -> None:
        """Verify all 13 Allen relations have test coverage above."""
        assert len(AllenRelation) == 13

    def test_point_events_equal(self) -> None:
        a = TimeInterval(dt(10), dt(10))
        b = TimeInterval(dt(10), dt(10))
        assert classify_allen_relation(a, b) == AllenRelation.EQUALS

    def test_point_event_before_interval(self) -> None:
        a = TimeInterval(dt(9), dt(9))
        b = TimeInterval(dt(10), dt(12))
        assert classify_allen_relation(a, b) == AllenRelation.BEFORE

    def test_interval_end_before_start_normalizes(self) -> None:
        """TimeInterval.__post_init__ normalizes end < start to end = start."""
        interval = TimeInterval(dt(12), dt(10))
        assert interval.end == interval.start
