from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

import structlog

logger = structlog.get_logger(__name__)


class AllenRelation(StrEnum):
    """Allen's Interval Algebra — 13 temporal relations.

    Design ref: PROJECT.md Section 6.3
    """

    BEFORE = "BEFORE"
    MEETS = "MEETS"
    OVERLAPS = "OVERLAPS"
    STARTS = "STARTS"
    DURING = "DURING"
    FINISHES = "FINISHES"
    EQUALS = "EQUALS"
    AFTER = "AFTER"
    MET_BY = "MET_BY"
    OVERLAPPED_BY = "OVERLAPPED_BY"
    STARTED_BY = "STARTED_BY"
    CONTAINS = "CONTAINS"
    FINISHED_BY = "FINISHED_BY"


@dataclass
class TimeInterval:
    """A time interval with start and end."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end < self.start:
            self.end = self.start


def classify_allen_relation(a: TimeInterval, b: TimeInterval) -> AllenRelation:
    """Classify the Allen temporal relation between two intervals."""
    # EQUALS must be checked before MEETS/STARTS/FINISHES (point events)
    if a.start == b.start and a.end == b.end:
        return AllenRelation.EQUALS
    if a.end < b.start:
        return AllenRelation.BEFORE
    if a.end == b.start:
        return AllenRelation.MEETS
    if a.start < b.start and a.end > b.start and a.end < b.end:
        return AllenRelation.OVERLAPS
    if a.start == b.start and a.end < b.end:
        return AllenRelation.STARTS
    if a.start > b.start and a.end < b.end:
        return AllenRelation.DURING
    if a.start > b.start and a.end == b.end:
        return AllenRelation.FINISHES
    if a.start > b.end:
        return AllenRelation.AFTER
    if a.start == b.end:
        return AllenRelation.MET_BY
    if a.start > b.start and a.start < b.end and a.end > b.end:
        return AllenRelation.OVERLAPPED_BY
    if a.start == b.start and a.end > b.end:
        return AllenRelation.STARTED_BY
    if a.start < b.start and a.end > b.end:
        return AllenRelation.CONTAINS
    if a.start < b.start and a.end == b.end:
        return AllenRelation.FINISHED_BY
    # Fallback
    return AllenRelation.BEFORE
