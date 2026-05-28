"""
Property-based tests for auto-approval logic.

Validates:
- **Property 20: Auto-Approval Logic (Requirement 6.1)**
"""

import pytest
from decimal import Decimal
from datetime import datetime, date
from uuid import uuid4
from unittest.mock import MagicMock
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from ap_workflow.models.invoice import Invoice, InvoiceStatus
from ap_workflow.models.vendor_baseline import VendorBaseline
from ap_workflow.services.decision_engine import DecisionEngine


# --- Fixtures ---

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    mock_query = MagicMock()
    session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None
    return session


@pytest.fixture
def decision_engine(mock_db_session):
    """Create decision engine with mock session."""
    return DecisionEngine(db=mock_db_session)


# --- Property 20: Auto-Approval Logic ---
# **Validates: Requirement 6.1**

class TestAutoApprovalLogic:
    """Property tests for auto-approval logic."""

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        has_exceptions=st.booleans(),
        total_amount=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        auto_approve_max=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        final_severity=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approval_conditions(self, decision_engine, has_exceptions, total_amount, auto_approve_max, final_severity):
        """
        **Property**: Auto-approval should occur when:
        - no exceptions AND
        - total_amount < auto_approve_max AND
        - final_severity < 0.4
        **Validates: Requirement 6.1**
        """
        # Determine if should auto-approve
        should_approve = (
            not has_exceptions and
            total_amount < auto_approve_max and
            final_severity < 0.4
        )
        
        # Create mock objects for the method call
        from unittest.mock import MagicMock
        from ap_workflow.models.invoice import Invoice
        from ap_workflow.models.anomaly_detection import AnomalyDetection
        
        invoice = MagicMock(spec=Invoice)
        invoice.total_amount_usd = total_amount
        invoice.vendor_key = "TEST_VENDOR"
        
        exceptions = [] if not has_exceptions else [MagicMock()]
        
        anomaly = MagicMock(spec=AnomalyDetection)
        anomaly.final_severity = final_severity
        
        # Mock the get_auto_approve_threshold method
        decision_engine.get_auto_approve_threshold = MagicMock(return_value=auto_approve_max)
        
        result = decision_engine._should_auto_approve(
            invoice,
            exceptions,
            anomaly
        )
        
        assert result == should_approve

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        total_amount=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        auto_approve_max=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approval_amount_threshold(self, decision_engine, total_amount, auto_approve_max):
        """
        **Property**: Auto-approval should check total_amount < auto_approve_max.
        **Validates: Requirement 6.1**
        """
        # No exceptions, low severity
        result = decision_engine._should_auto_approve(
            has_exceptions=False,
            total_amount=total_amount,
            auto_approve_max=auto_approve_max,
            final_severity=0.2
        )
        
        # Should approve only if amount is below threshold
        expected = total_amount < auto_approve_max
        assert result == expected

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        final_severity=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approval_severity_threshold_0_4(self, decision_engine, final_severity):
        """
        **Property**: Auto-approval should check final_severity < 0.4.
        **Validates: Requirement 6.1**
        """
        # No exceptions, low amount
        result = decision_engine._should_auto_approve(
            has_exceptions=False,
            total_amount=1000.0,
            auto_approve_max=10000.0,
            final_severity=final_severity
        )
        
        # Should approve only if severity is below 0.4
        expected = final_severity < 0.4
        assert result == expected

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        has_exceptions=st.booleans()
    )
    def test_auto_approval_exception_check(self, decision_engine, has_exceptions):
        """
        **Property**: Auto-approval should NOT occur if has_exceptions = True.
        **Validates: Requirement 6.1**
        """
        result = decision_engine._should_auto_approve(
            has_exceptions=has_exceptions,
            total_amount=1000.0,
            auto_approve_max=10000.0,
            final_severity=0.2
        )
        
        # Should approve only if no exceptions
        expected = not has_exceptions
        assert result == expected

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        total_amount=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        auto_approve_max=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approval_amount_boundary(self, decision_engine, total_amount, auto_approve_max):
        """
        **Property**: Amount threshold should be strict (<, not <=).
        **Validates: Requirement 6.1**
        """
        # Test at boundary
        result_at_boundary = decision_engine._should_auto_approve(
            has_exceptions=False,
            total_amount=auto_approve_max,
            auto_approve_max=auto_approve_max,
            final_severity=0.2
        )
        
        # Should NOT approve at boundary (< not <=)
        assert result_at_boundary is False
        
        # Just below boundary should approve
        result_below = decision_engine._should_auto_approve(
            has_exceptions=False,
            total_amount=auto_approve_max - 0.01,
            auto_approve_max=auto_approve_max,
            final_severity=0.2
        )
        
        assert result_below is True

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        final_severity=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approval_severity_boundary(self, decision_engine, final_severity):
        """
        **Property**: Severity threshold should be strict (<, not <=).
        **Validates: Requirement 6.1**
        """
        # Test at boundary
        result_at_boundary = decision_engine._should_auto_approve(
            has_exceptions=False,
            total_amount=1000.0,
            auto_approve_max=10000.0,
            final_severity=0.4
        )
        
        # Should NOT approve at boundary (< not <=)
        assert result_at_boundary is False
        
        # Just below boundary should approve
        result_below = decision_engine._should_auto_approve(
            has_exceptions=False,
            total_amount=1000.0,
            auto_approve_max=10000.0,
            final_severity=0.3999
        )
        
        assert result_below is True

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        total_amount=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        auto_approve_max=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        final_severity=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approval_deterministic(self, decision_engine, total_amount, auto_approve_max, final_severity):
        """
        **Property**: Auto-approval decision should be deterministic.
        **Validates: Requirement 6.1**
        """
        result_1 = decision_engine._should_auto_approve(
            has_exceptions=False,
            total_amount=total_amount,
            auto_approve_max=auto_approve_max,
            final_severity=final_severity
        )
        
        result_2 = decision_engine._should_auto_approve(
            has_exceptions=False,
            total_amount=total_amount,
            auto_approve_max=auto_approve_max,
            final_severity=final_severity
        )
        
        assert result_1 == result_2

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        total_amount=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        auto_approve_max=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approval_all_conditions_required(self, decision_engine, total_amount, auto_approve_max):
        """
        **Property**: ALL three conditions must be true for auto-approval (AND logic).
        **Validates: Requirement 6.1**
        """
        # Test each condition failing
        
        # Condition 1: has_exceptions = True (should fail)
        result_with_exceptions = decision_engine._should_auto_approve(
            has_exceptions=True,
            total_amount=total_amount,
            auto_approve_max=auto_approve_max,
            final_severity=0.2
        )
        assert result_with_exceptions is False
        
        # Condition 2: amount >= threshold (should fail)
        result_high_amount = decision_engine._should_auto_approve(
            has_exceptions=False,
            total_amount=auto_approve_max + 1.0,
            auto_approve_max=auto_approve_max,
            final_severity=0.2
        )
        assert result_high_amount is False
        
        # Condition 3: severity >= 0.4 (should fail)
        result_high_severity = decision_engine._should_auto_approve(
            has_exceptions=False,
            total_amount=total_amount,
            auto_approve_max=auto_approve_max,
            final_severity=0.5
        )
        assert result_high_severity is False

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        auto_approve_max=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approval_sets_approved_status(self, decision_engine, auto_approve_max):
        """
        **Property**: When auto-approved, invoice status should be set to APPROVED.
        **Validates: Requirement 6.1**
        """
        # Create mock invoice
        invoice = MagicMock()
        invoice.total_amount_usd = auto_approve_max - 1.0
        invoice.status = InvoiceStatus.PENDING_APPROVAL
        
        # Auto-approve
        decision_engine._auto_approve_invoice(invoice)
        
        # Status should be APPROVED
        assert invoice.status == InvoiceStatus.APPROVED

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        auto_approve_max=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approval_routes_to_payment_scheduler(self, decision_engine, auto_approve_max):
        """
        **Property**: When auto-approved, invoice should route to Payment_Scheduler.
        **Validates: Requirement 6.1**
        """
        # Create mock invoice
        invoice = MagicMock()
        invoice.total_amount_usd = auto_approve_max - 1.0
        
        # Auto-approve
        result = decision_engine._auto_approve_invoice(invoice)
        
        # Should return routing to payment scheduler
        assert result == "PAYMENT_SCHEDULER"


# --- Integration Tests ---

class TestAutoApprovalIntegration:
    """Integration tests for auto-approval logic."""

    def test_auto_approval_workflow_success(self, mock_db_session):
        """Test successful auto-approval workflow."""
        engine = DecisionEngine(db=mock_db_session)
        
        # Create invoice eligible for auto-approval
        invoice = MagicMock()
        invoice.total_amount_usd = 5000.0
        invoice.status = InvoiceStatus.PENDING_APPROVAL
        
        # Setup vendor baseline
        baseline = MagicMock()
        baseline.auto_approve_max_amount = Decimal("10000.00")
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = baseline
        
        # Should auto-approve
        result = engine._should_auto_approve(
            has_exceptions=False,
            total_amount=5000.0,
            auto_approve_max=10000.0,
            final_severity=0.2
        )
        
        assert result is True

    def test_auto_approval_workflow_failure_high_amount(self, mock_db_session):
        """Test auto-approval fails for high amount."""
        engine = DecisionEngine(db=mock_db_session)
        
        # Amount exceeds threshold
        result = engine._should_auto_approve(
            has_exceptions=False,
            total_amount=15000.0,
            auto_approve_max=10000.0,
            final_severity=0.2
        )
        
        assert result is False

    def test_auto_approval_workflow_failure_high_severity(self, mock_db_session):
        """Test auto-approval fails for high severity."""
        engine = DecisionEngine(db=mock_db_session)
        
        # Severity exceeds threshold
        result = engine._should_auto_approve(
            has_exceptions=False,
            total_amount=5000.0,
            auto_approve_max=10000.0,
            final_severity=0.5
        )
        
        assert result is False

    def test_auto_approval_workflow_failure_with_exceptions(self, mock_db_session):
        """Test auto-approval fails when exceptions exist."""
        engine = DecisionEngine(db=mock_db_session)
        
        # Has exceptions
        result = engine._should_auto_approve(
            has_exceptions=True,
            total_amount=5000.0,
            auto_approve_max=10000.0,
            final_severity=0.2
        )
        
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
