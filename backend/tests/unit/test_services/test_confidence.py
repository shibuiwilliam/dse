from __future__ import annotations

from dse.core.enums import EvidenceType
from dse.core.models import Evidence
from dse.workflows.activities.confidence import compute_confidence_update


class TestConfidenceUpdate:
    def test_user_correction_forces_value(self) -> None:
        evidence = Evidence(
            type=EvidenceType.USER_EXPLICIT_CORRECTION,
            forced_value=0.95,
        )
        result = compute_confidence_update(0.3, evidence)
        assert result == 0.95

    def test_user_correction_default_to_1(self) -> None:
        evidence = Evidence(type=EvidenceType.USER_EXPLICIT_CORRECTION)
        result = compute_confidence_update(0.3, evidence)
        assert result == 1.0

    def test_corroborating_source_increases(self) -> None:
        evidence = Evidence(
            type=EvidenceType.CORROBORATING_SOURCE,
            source_independent=True,
        )
        result = compute_confidence_update(0.5, evidence)
        assert result > 0.5

    def test_contradicting_source_decreases(self) -> None:
        evidence = Evidence(type=EvidenceType.CONTRADICTING_SOURCE)
        result = compute_confidence_update(0.5, evidence)
        assert result < 0.5

    def test_clamping_min(self) -> None:
        evidence = Evidence(type=EvidenceType.CONTRADICTING_SOURCE)
        result = compute_confidence_update(0.05, evidence)
        assert result >= 0.0

    def test_clamping_max(self) -> None:
        evidence = Evidence(
            type=EvidenceType.CORROBORATING_SOURCE,
            source_independent=True,
        )
        result = compute_confidence_update(0.95, evidence)
        assert result <= 1.0

    def test_independent_source_stronger_than_dependent(self) -> None:
        independent = Evidence(
            type=EvidenceType.CORROBORATING_SOURCE,
            source_independent=True,
        )
        dependent = Evidence(
            type=EvidenceType.CORROBORATING_SOURCE,
            source_independent=False,
        )
        ind_result = compute_confidence_update(0.5, independent)
        dep_result = compute_confidence_update(0.5, dependent)
        assert ind_result > dep_result

    def test_passage_of_time_decreases(self) -> None:
        evidence = Evidence(type=EvidenceType.PASSAGE_OF_TIME)
        result = compute_confidence_update(0.5, evidence)
        assert result < 0.5

    def test_repeated_access_increases(self) -> None:
        evidence = Evidence(type=EvidenceType.REPEATED_ACCESS)
        result = compute_confidence_update(0.5, evidence)
        assert result > 0.5

    def test_relation_derived_decreases(self) -> None:
        evidence = Evidence(type=EvidenceType.RELATION_DERIVED)
        result = compute_confidence_update(0.5, evidence)
        assert result < 0.5
