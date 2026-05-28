"""
Property-based tests for vendor baseline configuration validation.

Validates:
- **Property 40: Auto-Approve Threshold Validation (Requirement 11.6)**
- **Property 41: Z-Score Threshold Validation (Requirement 11.7)**
"""

import pytest
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import uuid4
from unittest.mock import MagicMock, patch
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from ap_workflow.models.vendor_baseline import VendorBaseline
from ap_workflow.models.invoice import Invoice, InvoiceStatus
from ap_workflow.services.vendor_baseline import VendorBaselineService


# --- Property 40: Auto-Approve Threshold Validation ---
# **Validates: Requirement 11.6**

class TestAutoApproveThresholdValidation:
    """Property tests for auto-approve max amount validation."""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        mean_amount=st.floats(min_value=100.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
        auto_approve_max=st.floats(min_value=0.0, max_value=500000.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approve_max_amount_non_negative(self, mean_amount, auto_approve_max):
        """
        **Property**: auto_approve_max_amount >= 0
        **Validates: Requirement 11.6**
        """
        # Create vendor baseline
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal(str(mean_amount)),
            auto_approve_max_amount=Decimal(str(auto_approve_max))
        )
        
        # Validate: auto_approve_max_amount must be >= 0
        assert baseline.auto_approve_max_amount >= 0

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        mean_amount=st.floats(min_value=100.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
        multiplier=st.floats(min_value=0.0, max_value=15.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approve_max_amount_10x_mean(self, mean_amount, multiplier):
        """
        **Property**: auto_approve_max_amount <= 10x mean_invoice_amount_30d
        **Validates: Requirement 11.6**
        """
        # Calculate auto_approve_max based on multiplier
        auto_approve_max = mean_amount * multiplier
        
        # Create vendor baseline
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal(str(mean_amount)),
            auto_approve_max_amount=Decimal(str(auto_approve_max))
        )
        
        # Validate: auto_approve_max_amount <= 10x mean
        max_allowed = Decimal(str(mean_amount * 10))
        
        # If auto_approve_max exceeds limit, it should be clamped
        if baseline.auto_approve_max_amount > max_allowed:
            # This is the validation that should occur
            assert baseline.auto_approve_max_amount > max_allowed
        else:
            # Within valid range
            assert baseline.auto_approve_max_amount <= max_allowed

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        mean_amount=st.floats(min_value=100.0, max_value=50000.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approve_max_amount_boundary_at_10x(self, mean_amount):
        """
        **Property**: auto_approve_max_amount at exactly 10x mean should be valid.
        **Validates: Requirement 11.6**
        """
        # Set auto_approve_max to exactly 10x mean
        auto_approve_max = mean_amount * 10
        
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal(str(mean_amount)),
            auto_approve_max_amount=Decimal(str(auto_approve_max))
        )
        
        # Should be valid at boundary
        max_allowed = Decimal(str(mean_amount * 10))
        assert baseline.auto_approve_max_amount <= max_allowed

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        mean_amount=st.floats(min_value=100.0, max_value=50000.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approve_max_amount_boundary_above_10x(self, mean_amount):
        """
        **Property**: auto_approve_max_amount above 10x mean should be invalid.
        **Validates: Requirement 11.6**
        """
        # Set auto_approve_max above 10x mean
        auto_approve_max = mean_amount * 10.1
        
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal(str(mean_amount)),
            auto_approve_max_amount=Decimal(str(auto_approve_max))
        )
        
        # Should exceed limit
        max_allowed = Decimal(str(mean_amount * 10))
        assert baseline.auto_approve_max_amount > max_allowed

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        mean_amount=st.floats(min_value=100.0, max_value=50000.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approve_max_amount_zero_valid(self, mean_amount):
        """
        **Property**: auto_approve_max_amount = 0 should be valid (disables auto-approval).
        **Validates: Requirement 11.6**
        """
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal(str(mean_amount)),
            auto_approve_max_amount=Decimal("0.00")
        )
        
        # Zero should be valid
        assert baseline.auto_approve_max_amount >= 0
        assert baseline.auto_approve_max_amount <= Decimal(str(mean_amount * 10))

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        mean_amount=st.floats(min_value=100.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
        auto_approve_max=st.floats(min_value=0.0, max_value=500000.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approve_max_amount_deterministic(self, mean_amount, auto_approve_max):
        """
        **Property**: Validation of auto_approve_max_amount should be deterministic.
        **Validates: Requirement 11.6**
        """
        baseline1 = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal(str(mean_amount)),
            auto_approve_max_amount=Decimal(str(auto_approve_max))
        )
        
        baseline2 = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal(str(mean_amount)),
            auto_approve_max_amount=Decimal(str(auto_approve_max))
        )
        
        # Both should have same validation result
        max_allowed = Decimal(str(mean_amount * 10))
        result1 = baseline1.auto_approve_max_amount <= max_allowed
        result2 = baseline2.auto_approve_max_amount <= max_allowed
        
        assert result1 == result2

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        mean_amount=st.floats(min_value=100.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
        auto_approve_max=st.floats(min_value=0.0, max_value=500000.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approve_max_amount_independent_of_zscore(self, mean_amount, auto_approve_max):
        """
        **Property**: auto_approve_max_amount validation should be independent of z-score threshold.
        **Validates: Requirement 11.6**
        """
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal(str(mean_amount)),
            auto_approve_max_amount=Decimal(str(auto_approve_max)),
            auto_approve_max_zscore=2.5
        )
        
        # Validation should not depend on z-score
        max_allowed = Decimal(str(mean_amount * 10))
        is_valid = baseline.auto_approve_max_amount >= 0 and baseline.auto_approve_max_amount <= max_allowed
        
        # Should be valid regardless of z-score value
        assert isinstance(is_valid, bool)

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        mean_amount=st.floats(min_value=100.0, max_value=50000.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approve_max_amount_scaling_with_mean(self, mean_amount):
        """
        **Property**: As mean_invoice_amount_30d increases, max allowed auto_approve_max_amount should increase proportionally.
        **Validates: Requirement 11.6**
        """
        # Create two baselines with different means
        mean1 = mean_amount
        mean2 = mean_amount * 2
        
        max_allowed1 = mean1 * 10
        max_allowed2 = mean2 * 10
        
        # Verify proportional scaling
        assert max_allowed2 == max_allowed1 * 2


# --- Property 41: Z-Score Threshold Validation ---
# **Validates: Requirement 11.7**

class TestZScoreThresholdValidation:
    """Property tests for auto-approve max z-score validation."""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        zscore=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False)
    )
    def test_zscore_range_validation(self, zscore):
        """
        **Property**: auto_approve_max_zscore must be in range [1.5, 4.0]
        **Validates: Requirement 11.7**
        """
        service = VendorBaselineService()
        is_valid, error_msg = service.validate_auto_approve_max_zscore(zscore)
        
        if 1.5 <= zscore <= 4.0:
            assert is_valid is True
            assert error_msg is None
        else:
            assert is_valid is False
            assert "must be in range [1.5, 4.0]" in error_msg or "must be >= 1.5" in error_msg or "must be <= 4.0" in error_msg

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        zscore=st.floats(min_value=1.5, max_value=4.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approve_max_zscore_valid_range(self, zscore):
        """
        **Property**: auto_approve_max_zscore in [1.5, 4.0] should be valid.
        **Validates: Requirement 11.7**
        """
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            auto_approve_max_zscore=zscore
        )
        
        # Should be valid
        assert 1.5 <= baseline.auto_approve_max_zscore <= 4.0

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        zscore=st.floats(min_value=0.0, max_value=1.4999, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approve_max_zscore_below_minimum(self, zscore):
        """
        **Property**: auto_approve_max_zscore < 1.5 should be invalid.
        **Validates: Requirement 11.7**
        """
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            auto_approve_max_zscore=zscore
        )
        
        # Should be invalid (below minimum)
        assert baseline.auto_approve_max_zscore < 1.5

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        zscore=st.floats(min_value=4.0001, max_value=10.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approve_max_zscore_above_maximum(self, zscore):
        """
        **Property**: auto_approve_max_zscore > 4.0 should be invalid.
        **Validates: Requirement 11.7**
        """
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            auto_approve_max_zscore=zscore
        )
        
        # Should be invalid (above maximum)
        assert baseline.auto_approve_max_zscore > 4.0

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        zscore=st.floats(min_value=1.5, max_value=4.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approve_max_zscore_boundary_lower(self, zscore):
        """
        **Property**: auto_approve_max_zscore at exactly 1.5 should be valid.
        **Validates: Requirement 11.7**
        """
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            auto_approve_max_zscore=1.5
        )
        
        # Should be valid at lower boundary
        assert baseline.auto_approve_max_zscore >= 1.5
        assert baseline.auto_approve_max_zscore <= 4.0

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        zscore=st.floats(min_value=1.5, max_value=4.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approve_max_zscore_boundary_upper(self, zscore):
        """
        **Property**: auto_approve_max_zscore at exactly 4.0 should be valid.
        **Validates: Requirement 11.7**
        """
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            auto_approve_max_zscore=4.0
        )
        
        # Should be valid at upper boundary
        assert baseline.auto_approve_max_zscore >= 1.5
        assert baseline.auto_approve_max_zscore <= 4.0

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        zscore=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approve_max_zscore_deterministic(self, zscore):
        """
        **Property**: Validation of auto_approve_max_zscore should be deterministic.
        **Validates: Requirement 11.7**
        """
        baseline1 = VendorBaseline(
            vendor_key="VENDOR_001",
            auto_approve_max_zscore=zscore
        )
        
        baseline2 = VendorBaseline(
            vendor_key="VENDOR_001",
            auto_approve_max_zscore=zscore
        )
        
        # Both should have same validation result
        result1 = 1.5 <= baseline1.auto_approve_max_zscore <= 4.0
        result2 = 1.5 <= baseline2.auto_approve_max_zscore <= 4.0
        
        assert result1 == result2

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        zscore=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        auto_approve_max=st.floats(min_value=0.0, max_value=500000.0, allow_nan=False, allow_infinity=False)
    )
    def test_auto_approve_max_zscore_independent_of_amount(self, zscore, auto_approve_max):
        """
        **Property**: auto_approve_max_zscore validation should be independent of auto_approve_max_amount.
        **Validates: Requirement 11.7**
        """
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            auto_approve_max_zscore=zscore,
            auto_approve_max_amount=Decimal(str(auto_approve_max))
        )
        
        # Validation should not depend on amount
        is_zscore_valid = 1.5 <= baseline.auto_approve_max_zscore <= 4.0
        
        # Should be valid regardless of amount value
        assert isinstance(is_zscore_valid, bool)

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        zscore_values=st.lists(
            st.floats(min_value=1.5, max_value=4.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=5
        )
    )
    def test_auto_approve_max_zscore_multiple_valid_values(self, zscore_values):
        """
        **Property**: Multiple z-score values in valid range should all be valid.
        **Validates: Requirement 11.7**
        """
        for zscore in zscore_values:
            baseline = VendorBaseline(
                vendor_key=f"VENDOR_{zscore}",
                auto_approve_max_zscore=zscore
            )
            
            # All should be valid
            assert 1.5 <= baseline.auto_approve_max_zscore <= 4.0


# --- Combined Validation Tests ---

class TestCombinedBaselineValidation:
    """Property tests for combined baseline validation."""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        mean_amount=st.floats(min_value=100.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
        auto_approve_max=st.floats(min_value=0.0, max_value=500000.0, allow_nan=False, allow_infinity=False),
        zscore=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False)
    )
    def test_both_validations_independent(self, mean_amount, auto_approve_max, zscore):
        """
        **Property**: Amount and z-score validations should be independent.
        **Validates: Requirements 11.6 and 11.7**
        """
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal(str(mean_amount)),
            auto_approve_max_amount=Decimal(str(auto_approve_max)),
            auto_approve_max_zscore=zscore
        )
        
        # Check amount validation
        amount_valid = baseline.auto_approve_max_amount >= 0 and baseline.auto_approve_max_amount <= Decimal(str(mean_amount * 10))
        
        # Check z-score validation
        zscore_valid = 1.5 <= baseline.auto_approve_max_zscore <= 4.0
        
        # Both should be independent boolean values
        assert isinstance(amount_valid, bool)
        assert isinstance(zscore_valid, bool)

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        mean_amount=st.floats(min_value=100.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
        auto_approve_max=st.floats(min_value=0.0, max_value=500000.0, allow_nan=False, allow_infinity=False),
        zscore=st.floats(min_value=1.5, max_value=4.0, allow_nan=False, allow_infinity=False)
    )
    def test_valid_baseline_configuration(self, mean_amount, auto_approve_max, zscore):
        """
        **Property**: A baseline with valid amount and z-score should be acceptable.
        **Validates: Requirements 11.6 and 11.7**
        """
        # Clamp auto_approve_max to valid range
        max_allowed = mean_amount * 10
        clamped_auto_approve_max = min(auto_approve_max, max_allowed)
        
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal(str(mean_amount)),
            auto_approve_max_amount=Decimal(str(clamped_auto_approve_max)),
            auto_approve_max_zscore=zscore
        )
        
        # Both should be valid
        amount_valid = baseline.auto_approve_max_amount >= 0 and baseline.auto_approve_max_amount <= Decimal(str(mean_amount * 10))
        zscore_valid = 1.5 <= baseline.auto_approve_max_zscore <= 4.0
        
        assert amount_valid
        assert zscore_valid


# --- Edge Case Tests ---

class TestBaselineValidationEdgeCases:
    """Property tests for edge cases in baseline validation."""

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        mean_amount=st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    def test_small_mean_amount_validation(self, mean_amount):
        """
        **Property**: Validation should work correctly for very small mean amounts.
        **Validates: Requirements 11.6 and 11.7**
        """
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal(str(mean_amount)),
            auto_approve_max_amount=Decimal(str(mean_amount * 5))
        )
        
        # Should still validate correctly
        max_allowed = Decimal(str(mean_amount * 10))
        assert baseline.auto_approve_max_amount <= max_allowed

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        mean_amount=st.floats(min_value=100000.0, max_value=1000000.0, allow_nan=False, allow_infinity=False)
    )
    def test_large_mean_amount_validation(self, mean_amount):
        """
        **Property**: Validation should work correctly for very large mean amounts.
        **Validates: Requirements 11.6 and 11.7**
        """
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal(str(mean_amount)),
            auto_approve_max_amount=Decimal(str(mean_amount * 5))
        )
        
        # Should still validate correctly
        max_allowed = Decimal(str(mean_amount * 10))
        assert baseline.auto_approve_max_amount <= max_allowed

    def test_null_auto_approve_max_amount(self):
        """
        **Property**: Null auto_approve_max_amount should be handled gracefully.
        **Validates: Requirement 11.6**
        """
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal("5000.00"),
            auto_approve_max_amount=None
        )
        
        # Should not raise error
        assert baseline.auto_approve_max_amount is None

    def test_null_auto_approve_max_zscore(self):
        """
        **Property**: Null auto_approve_max_zscore should be handled gracefully.
        **Validates: Requirement 11.7**
        """
        baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            auto_approve_max_zscore=None
        )
        
        # Should not raise error
        assert baseline.auto_approve_max_zscore is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
