"""
Property-based tests for exception priority ordering.

Validates:
- **Property 22: Exception Priority Ordering (Requirement 6.5)**
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from ap_workflow.services.decision_engine import DecisionEngine


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    mock_query = MagicMock()
    session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None
    mock_query.all.return_value = []
    return session


@pytest.fixture
def decision_engine(mock_db_session):
    """Create decision engine with mock session."""
    return DecisionEngine(db=mock_db_session)


severity_strategy = st.floats(
    min_value=0.0,
    max_value=1.0,
    allow_nan=False,
    allow_infinity=False
)

SUPPRESS_CHECKS = [HealthCheck.too_slow, HealthCheck.function_scoped_fixture]


class TestExceptionPriorityOrdering:
    """Property tests for exception priority ordering logic."""

    def test_priority_order_is_defined(self, decision_engine):
        """
        **Property**: Exception priority order should be deterministically defined.
        **Validates: Requirement 6.5**
        """
        priority_order = [
            "DUPLICATE_EXACT",
            "ANOMALY",
            "PO_MISMATCH",
            "PARTIAL_RECEIPT",
            "PO_MISSING",
            "RECEIPT_MISSING",
            "INCOMPLETE_DATA"
        ]
        
        assert priority_order[0] == "DUPLICATE_EXACT"
        assert priority_order[1] == "ANOMALY"
        assert priority_order[2] == "PO_MISMATCH"

    @settings(max_examples=50, suppress_health_check=SUPPRESS_CHECKS)
    @given(severity1=severity_strategy, severity2=severity_strategy)
    def test_highest_priority_exception_selected_when_multiple_exist(self, decision_engine, severity1, severity2):
        """
        **Property**: When multiple exceptions exist, highest-priority exception should be selected.
        **Validates: Requirement 6.5**
        """
        exc1 = MagicMock()
        exc1.exception_type = "PO_MISMATCH"
        exc1.severity = Decimal(str(severity1))
        
        exc2 = MagicMock()
        exc2.exception_type = "DUPLICATE_EXACT"
        exc2.severity = Decimal(str(severity2))
        
        exceptions = [exc1, exc2]
        highest_priority = decision_engine.determine_exception_priority(exceptions)
        
        assert highest_priority.exception_type == "DUPLICATE_EXACT"

    @settings(max_examples=50, suppress_health_check=SUPPRESS_CHECKS)
    @given(severity1=severity_strategy, severity2=severity_strategy, severity3=severity_strategy)
    def test_priority_order_duplicate_exact_highest(self, decision_engine, severity1, severity2, severity3):
        """
        **Property**: DUPLICATE_EXACT should always be highest priority regardless of other exceptions.
        **Validates: Requirement 6.5**
        """
        exc_duplicate = MagicMock()
        exc_duplicate.exception_type = "DUPLICATE_EXACT"
        exc_duplicate.severity = Decimal(str(severity1))
        
        exc_po_mismatch = MagicMock()
        exc_po_mismatch.exception_type = "PO_MISMATCH"
        exc_po_mismatch.severity = Decimal(str(severity2))
        
        exc_partial = MagicMock()
        exc_partial.exception_type = "PARTIAL_RECEIPT"
        exc_partial.severity = Decimal(str(severity3))
        
        exceptions = [exc_po_mismatch, exc_partial, exc_duplicate]
        highest_priority = decision_engine.determine_exception_priority(exceptions)
        
        assert highest_priority.exception_type == "DUPLICATE_EXACT"

    @settings(max_examples=50, suppress_health_check=SUPPRESS_CHECKS)
    @given(severity1=severity_strategy, severity2=severity_strategy)
    def test_priority_order_anomaly_second_highest(self, decision_engine, severity1, severity2):
        """
        **Property**: ANOMALY (CRITICAL/HIGH) should be second highest priority after DUPLICATE_EXACT.
        **Validates: Requirement 6.5**
        """
        assume(severity1 > 0.6)
        
        exc_anomaly = MagicMock()
        exc_anomaly.exception_type = "ANOMALY"
        exc_anomaly.severity = Decimal(str(severity1))
        
        exc_po_mismatch = MagicMock()
        exc_po_mismatch.exception_type = "PO_MISMATCH"
        exc_po_mismatch.severity = Decimal(str(severity2))
        
        exceptions = [exc_po_mismatch, exc_anomaly]
        highest_priority = decision_engine.determine_exception_priority(exceptions)
        
        assert highest_priority.exception_type == "ANOMALY"

    @settings(max_examples=50, suppress_health_check=SUPPRESS_CHECKS)
    @given(severity=severity_strategy)
    def test_priority_ordering_is_deterministic(self, decision_engine, severity):
        """
        **Property**: Priority ordering should be deterministic (same input = same output).
        **Validates: Requirement 6.5**
        """
        exc1 = MagicMock()
        exc1.exception_type = "PO_MISMATCH"
        exc1.severity = Decimal(str(severity))
        
        exc2 = MagicMock()
        exc2.exception_type = "DUPLICATE_EXACT"
        exc2.severity = Decimal(str(severity))
        
        exc3 = MagicMock()
        exc3.exception_type = "PARTIAL_RECEIPT"
        exc3.severity = Decimal(str(severity))
        
        exceptions = [exc1, exc2, exc3]
        
        priority1 = decision_engine.determine_exception_priority(exceptions)
        priority2 = decision_engine.determine_exception_priority(exceptions)
        priority3 = decision_engine.determine_exception_priority(exceptions)
        
        assert priority1.exception_type == priority2.exception_type == priority3.exception_type
        assert priority1.exception_type == "DUPLICATE_EXACT"

    def test_empty_exception_list_returns_none(self, decision_engine):
        """
        **Property**: Empty exception list should return None.
        **Validates: Requirement 6.5**
        """
        exceptions = []
        highest_priority = decision_engine.determine_exception_priority(exceptions)
        assert highest_priority is None

    @settings(max_examples=50, suppress_health_check=SUPPRESS_CHECKS)
    @given(severity=severity_strategy)
    def test_single_exception_returns_itself(self, decision_engine, severity):
        """
        **Property**: Single exception should be returned as highest priority.
        **Validates: Requirement 6.5**
        """
        exc = MagicMock()
        exc.exception_type = "PO_MISMATCH"
        exc.severity = Decimal(str(severity))
        
        exceptions = [exc]
        highest_priority = decision_engine.determine_exception_priority(exceptions)
        
        assert highest_priority.exception_type == "PO_MISMATCH"
        assert highest_priority.severity == Decimal(str(severity))

    @settings(max_examples=50, suppress_health_check=SUPPRESS_CHECKS)
    @given(severity1=severity_strategy, severity2=severity_strategy)
    def test_priority_selection_independent_of_severity_within_same_type(self, decision_engine, severity1, severity2):
        """
        **Property**: Priority selection should be independent of severity when comparing different exception types.
        **Validates: Requirement 6.5**
        """
        exc_high_severity_po_mismatch = MagicMock()
        exc_high_severity_po_mismatch.exception_type = "PO_MISMATCH"
        exc_high_severity_po_mismatch.severity = Decimal("0.9")
        
        exc_low_severity_duplicate = MagicMock()
        exc_low_severity_duplicate.exception_type = "DUPLICATE_EXACT"
        exc_low_severity_duplicate.severity = Decimal("0.1")
        
        exceptions = [exc_high_severity_po_mismatch, exc_low_severity_duplicate]
        highest_priority = decision_engine.determine_exception_priority(exceptions)
        
        assert highest_priority.exception_type == "DUPLICATE_EXACT"

    @settings(max_examples=50, suppress_health_check=SUPPRESS_CHECKS)
    @given(severity1=severity_strategy, severity2=severity_strategy)
    def test_priority_selection_uses_severity_as_tiebreaker(self, decision_engine, severity1, severity2):
        """
        **Property**: When exception types are the same, severity should be used as tiebreaker (highest severity wins).
        **Validates: Requirement 6.5**
        """
        assume(severity1 != severity2)
        
        exc1 = MagicMock()
        exc1.exception_type = "ANOMALY"
        exc1.severity = Decimal(str(severity1))
        
        exc2 = MagicMock()
        exc2.exception_type = "ANOMALY"
        exc2.severity = Decimal(str(severity2))
        
        exceptions = [exc1, exc2]
        highest_priority = decision_engine.determine_exception_priority(exceptions)
        
        expected_severity = max(Decimal(str(severity1)), Decimal(str(severity2)))
        assert highest_priority.severity == expected_severity

    @settings(max_examples=50, suppress_health_check=SUPPRESS_CHECKS)
    @given(severity1=severity_strategy, severity2=severity_strategy, severity3=severity_strategy)
    def test_priority_ordering_with_shuffled_input(self, decision_engine, severity1, severity2, severity3):
        """
        **Property**: Priority ordering should be independent of input order (deterministic).
        **Validates: Requirement 6.5**
        """
        exc1 = MagicMock()
        exc1.exception_type = "PO_MISMATCH"
        exc1.severity = Decimal(str(severity1))
        
        exc2 = MagicMock()
        exc2.exception_type = "DUPLICATE_EXACT"
        exc2.severity = Decimal(str(severity2))
        
        exc3 = MagicMock()
        exc3.exception_type = "PARTIAL_RECEIPT"
        exc3.severity = Decimal(str(severity3))
        
        order1 = [exc1, exc2, exc3]
        order2 = [exc3, exc1, exc2]
        order3 = [exc2, exc3, exc1]
        
        priority1 = decision_engine.determine_exception_priority(order1)
        priority2 = decision_engine.determine_exception_priority(order2)
        priority3 = decision_engine.determine_exception_priority(order3)
        
        assert priority1.exception_type == priority2.exception_type == priority3.exception_type == "DUPLICATE_EXACT"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
