"""
Property-based tests for Z-Score anomaly detection.

Validates:
- **Property 16: Z-Score Anomaly Detection (Requirement 5.1)**
"""

import pytest
import statistics
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import uuid4
from unittest.mock import MagicMock
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from ap_workflow.models.invoice import Invoice, InvoiceStatus
from ap_workflow.models.vendor_baseline import VendorBaseline
from ap_workflow.services.anomaly_detection import AnomalyDetectionService


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
def anomaly_service(mock_db_session):
    """Create anomaly detection service with mock session."""
    return AnomalyDetectionService(db=mock_db_session)


# --- Property 16: Z-Score Anomaly Detection ---
# **Validates: Requirement 5.1**

class TestZScoreAnomalyDetection:
    """Property tests for Z-Score anomaly detection."""

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        amount=st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        mean=st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        std_dev=st.floats(min_value=0.1, max_value=5000.0, allow_nan=False, allow_infinity=False)
    )
    def test_zscore_calculation_correctness(self, anomaly_service, amount, mean, std_dev):
        """
        **Property**: Z-Score should be calculated as (amount - mean) / std_dev.
        **Validates: Requirement 5.1**
        """
        expected_zscore = (amount - mean) / std_dev
        
        result_zscore = anomaly_service._calculate_zscore(amount, mean, std_dev)
        
        assert abs(result_zscore - expected_zscore) < 0.001

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        zscore=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False)
    )
    def test_zscore_severity_calculation(self, anomaly_service, zscore):
        """
        **Property**: Severity should be min(1.0, |z_score| / 6.0) if |z_score| > 2.5, else 0.0.
        **Validates: Requirement 5.1**
        """
        if abs(zscore) > 2.5:
            expected_severity = min(1.0, abs(zscore) / 6.0)
        else:
            expected_severity = 0.0
        
        result_severity = anomaly_service._calculate_zscore_severity(zscore)
        
        assert abs(result_severity - expected_severity) < 0.001

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        zscore=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False)
    )
    def test_zscore_severity_in_valid_range(self, anomaly_service, zscore):
        """
        **Property**: Z-Score severity should always be in range [0.0, 1.0].
        **Validates: Requirement 5.1**
        """
        severity = anomaly_service._calculate_zscore_severity(zscore)
        
        assert 0.0 <= severity <= 1.0

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        zscore_value=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False)
    )
    def test_zscore_threshold_2_5(self, anomaly_service, zscore_value):
        """
        **Property**: Z-Score anomaly should be detected when |z_score| > 2.5.
        **Validates: Requirement 5.1**
        """
        is_anomaly = anomaly_service._is_zscore_anomaly(zscore_value)
        
        expected = abs(zscore_value) > 2.5
        assert is_anomaly == expected

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        num_transactions=st.integers(min_value=1, max_value=50)
    )
    def test_zscore_requires_minimum_transactions(self, anomaly_service, num_transactions):
        """
        **Property**: Z-Score should only be computed for vendors with >=10 transactions in past 30 days.
        **Validates: Requirement 5.1**
        """
        # Requirement: "Compute rolling Z-Score for vendors with >=10 transactions in past 30 days"
        
        if num_transactions >= 10:
            # Should compute Z-Score
            can_compute = True
        else:
            # Should skip Z-Score
            can_compute = False
        
        result = anomaly_service._can_compute_zscore(num_transactions)
        
        assert result == can_compute

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        amounts=st.lists(
            st.floats(min_value=100.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
            min_size=10,
            max_size=50
        )
    )
    def test_zscore_with_historical_data(self, anomaly_service, amounts):
        """
        **Property**: Z-Score should be computed correctly using historical data.
        **Validates: Requirement 5.1**
        """
        # Compute mean and std dev
        mean = statistics.mean(amounts)
        std_dev = statistics.stdev(amounts) if len(amounts) > 1 else 0.0
        
        # Test new amount (first amount in list)
        new_amount = amounts[0]
        
        if std_dev > 0:
            expected_zscore = (new_amount - mean) / std_dev
        else:
            expected_zscore = 0.0
        
        result_zscore = anomaly_service._calculate_zscore(new_amount, mean, std_dev)
        
        assert abs(result_zscore - expected_zscore) < 0.001

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        zscore_1=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        zscore_2=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False)
    )
    def test_zscore_severity_monotonic_with_magnitude(self, anomaly_service, zscore_1, zscore_2):
        """
        **Property**: Severity should increase monotonically with |z_score| magnitude.
        **Validates: Requirement 5.1**
        """
        severity_1 = anomaly_service._calculate_zscore_severity(zscore_1)
        severity_2 = anomaly_service._calculate_zscore_severity(zscore_2)
        
        # If |zscore_1| > |zscore_2|, then severity_1 >= severity_2
        if abs(zscore_1) > abs(zscore_2):
            assert severity_1 >= severity_2
        elif abs(zscore_1) < abs(zscore_2):
            assert severity_1 <= severity_2
        else:
            assert severity_1 == severity_2

    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    @given(
        zscore=st.floats(min_value=2.5, max_value=10.0, allow_nan=False, allow_infinity=False)
    )
    def test_zscore_severity_capped_at_1_0(self, anomaly_service, zscore):
        """
        **Property**: Z-Score severity should never exceed 1.0 (capped).
        **Validates: Requirement 5.1**
        """
        severity = anomaly_service._calculate_zscore_severity(zscore)
        
        assert severity <= 1.0

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        amount=st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        mean=st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        std_dev=st.floats(min_value=0.1, max_value=5000.0, allow_nan=False, allow_infinity=False)
    )
    def test_zscore_deterministic(self, anomaly_service, amount, mean, std_dev):
        """
        **Property**: Z-Score calculation should be deterministic (same inputs = same output).
        **Validates: Requirement 5.1**
        """
        zscore_1 = anomaly_service._calculate_zscore(amount, mean, std_dev)
        zscore_2 = anomaly_service._calculate_zscore(amount, mean, std_dev)
        
        assert zscore_1 == zscore_2

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        num_invoices=st.integers(min_value=2, max_value=100)
    )
    def test_zscore_with_varying_invoice_counts(self, anomaly_service, num_invoices):
        """
        **Property**: Z-Score should handle varying numbers of historical invoices.
        **Validates: Requirement 5.1**
        """
        # Generate amounts
        amounts = [float(100 + i * 10) for i in range(num_invoices)]
        
        mean = statistics.mean(amounts)
        std_dev = statistics.stdev(amounts) if len(amounts) > 1 else 0.0
        
        # Test with new amount
        new_amount = 150.0
        
        if std_dev > 0:
            zscore = (new_amount - mean) / std_dev
        else:
            zscore = 0.0
        
        result = anomaly_service._calculate_zscore(new_amount, mean, std_dev)
        
        assert abs(result - zscore) < 0.001


# --- Integration Tests ---

class TestZScoreAnomalyIntegration:
    """Integration tests for Z-Score anomaly detection."""

    def test_zscore_anomaly_detection_workflow(self, mock_db_session):
        """Test complete Z-Score anomaly detection workflow."""
        service = AnomalyDetectionService(db=mock_db_session)
        
        # Setup vendor baseline
        baseline = MagicMock()
        baseline.mean_invoice_amount_30d = Decimal("1000.00")
        baseline.std_invoice_amount_30d = Decimal("100.00")
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = baseline
        
        # Test with anomalous amount (3 std devs above mean)
        anomalous_amount = 1300.0
        
        zscore = (anomalous_amount - 1000.0) / 100.0
        severity = service._calculate_zscore_severity(zscore)
        
        # Should be detected as anomaly
        assert severity > 0.0

    def test_zscore_normal_amount_no_anomaly(self, mock_db_session):
        """Test that normal amounts don't trigger anomaly."""
        service = AnomalyDetectionService(db=mock_db_session)
        
        # Normal amount (within 1 std dev)
        normal_amount = 1050.0
        mean = 1000.0
        std_dev = 100.0
        
        zscore = (normal_amount - mean) / std_dev
        severity = service._calculate_zscore_severity(zscore)
        
        # Should not be detected as anomaly
        assert severity == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
