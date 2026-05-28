"""Unit tests for vendor baseline configuration validation."""

import pytest
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import uuid4
from unittest.mock import MagicMock, patch

from ap_workflow.models.vendor_baseline import VendorBaseline
from ap_workflow.models.invoice import Invoice, InvoiceStatus
from ap_workflow.services.vendor_baseline import VendorBaselineService, BaselineValidationError


class TestBaselineValidationService:
    """Unit tests for baseline validation service."""

    def test_validate_auto_approve_max_amount_non_negative(self):
        """Test that auto_approve_max_amount must be >= 0."""
        service = VendorBaselineService(db=MagicMock())
        
        # Valid: 0
        is_valid, error_msg = service.validate_auto_approve_max_amount(
            Decimal("0.00"),
            Decimal("5000.00")
        )
        assert is_valid
        assert error_msg is None
        
        # Valid: positive
        is_valid, error_msg = service.validate_auto_approve_max_amount(
            Decimal("10000.00"),
            Decimal("5000.00")
        )
        assert is_valid
        assert error_msg is None
        
        # Invalid: negative
        is_valid, error_msg = service.validate_auto_approve_max_amount(
            Decimal("-100.00"),
            Decimal("5000.00")
        )
        assert not is_valid
        assert "must be >= 0" in error_msg

    def test_validate_auto_approve_max_amount_10x_mean(self):
        """Test that auto_approve_max_amount <= 10x mean_invoice_amount_30d."""
        service = VendorBaselineService(db=MagicMock())
        
        mean_amount = Decimal("5000.00")
        max_allowed = mean_amount * 10  # 50000
        
        # Valid: at boundary
        is_valid, error_msg = service.validate_auto_approve_max_amount(
            max_allowed,
            mean_amount
        )
        assert is_valid
        assert error_msg is None
        
        # Valid: below boundary
        is_valid, error_msg = service.validate_auto_approve_max_amount(
            Decimal("25000.00"),
            mean_amount
        )
        assert is_valid
        assert error_msg is None
        
        # Invalid: above boundary
        is_valid, error_msg = service.validate_auto_approve_max_amount(
            Decimal("50001.00"),
            mean_amount
        )
        assert not is_valid
        assert "must be <= 10x mean_invoice_amount_30d" in error_msg

    def test_validate_auto_approve_max_amount_null(self):
        """Test that null auto_approve_max_amount is valid."""
        service = VendorBaselineService(db=MagicMock())
        
        is_valid, error_msg = service.validate_auto_approve_max_amount(
            None,
            Decimal("5000.00")
        )
        assert is_valid
        assert error_msg is None

    def test_validate_auto_approve_max_amount_zero_mean(self):
        """Test validation when mean is zero."""
        service = VendorBaselineService(db=MagicMock())
        
        # Should be valid when mean is 0 (no upper limit check)
        is_valid, error_msg = service.validate_auto_approve_max_amount(
            Decimal("10000.00"),
            Decimal("0.00")
        )
        assert is_valid
        assert error_msg is None

    def test_validate_auto_approve_max_zscore_in_range(self):
        """Test that auto_approve_max_zscore must be in [1.5, 4.0]."""
        service = VendorBaselineService(db=MagicMock())
        
        # Valid: at lower boundary
        is_valid, error_msg = service.validate_auto_approve_max_zscore(1.5)
        assert is_valid
        assert error_msg is None
        
        # Valid: in middle
        is_valid, error_msg = service.validate_auto_approve_max_zscore(2.5)
        assert is_valid
        assert error_msg is None
        
        # Valid: at upper boundary
        is_valid, error_msg = service.validate_auto_approve_max_zscore(4.0)
        assert is_valid
        assert error_msg is None
        
        # Invalid: below minimum
        is_valid, error_msg = service.validate_auto_approve_max_zscore(1.4)
        assert not is_valid
        assert "must be >= 1.5" in error_msg
        
        # Invalid: above maximum
        is_valid, error_msg = service.validate_auto_approve_max_zscore(4.1)
        assert not is_valid
        assert "must be <= 4.0" in error_msg

    def test_validate_auto_approve_max_zscore_null(self):
        """Test that null auto_approve_max_zscore is valid."""
        service = VendorBaselineService(db=MagicMock())
        
        is_valid, error_msg = service.validate_auto_approve_max_zscore(None)
        assert is_valid
        assert error_msg is None

    def test_validate_baseline_configuration_both_valid(self):
        """Test validation when both amount and zscore are valid."""
        service = VendorBaselineService(db=MagicMock())
        
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=Decimal("25000.00"),
            auto_approve_max_zscore=2.5,
            mean_invoice_amount_30d=Decimal("5000.00")
        )
        assert is_valid
        assert error_msg is None

    def test_validate_baseline_configuration_invalid_amount(self):
        """Test validation when amount is invalid."""
        service = VendorBaselineService(db=MagicMock())
        
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=Decimal("60000.00"),  # > 10x mean
            auto_approve_max_zscore=2.5,
            mean_invoice_amount_30d=Decimal("5000.00")
        )
        assert not is_valid
        assert "must be <= 10x mean_invoice_amount_30d" in error_msg

    def test_validate_baseline_configuration_invalid_zscore(self):
        """Test validation when zscore is invalid."""
        service = VendorBaselineService(db=MagicMock())
        
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=Decimal("25000.00"),
            auto_approve_max_zscore=5.0,  # > 4.0
            mean_invoice_amount_30d=Decimal("5000.00")
        )
        assert not is_valid
        assert "must be <= 4.0" in error_msg

    def test_validate_baseline_configuration_both_invalid(self):
        """Test validation when both are invalid (returns first error)."""
        service = VendorBaselineService(db=MagicMock())
        
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=Decimal("60000.00"),  # > 10x mean
            auto_approve_max_zscore=5.0,  # > 4.0
            mean_invoice_amount_30d=Decimal("5000.00")
        )
        assert not is_valid
        # Should return first error (amount)
        assert "must be <= 10x mean_invoice_amount_30d" in error_msg

    def test_validate_baseline_configuration_partial_update(self):
        """Test validation with partial updates."""
        service = VendorBaselineService(db=MagicMock())
        
        # Only updating amount
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=Decimal("25000.00"),
            auto_approve_max_zscore=None,
            mean_invoice_amount_30d=Decimal("5000.00")
        )
        assert is_valid
        assert error_msg is None
        
        # Only updating zscore
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=None,
            auto_approve_max_zscore=2.5,
            mean_invoice_amount_30d=Decimal("5000.00")
        )
        assert is_valid
        assert error_msg is None

    def test_validate_baseline_configuration_edge_cases(self):
        """Test validation with edge cases."""
        service = VendorBaselineService(db=MagicMock())
        
        # Very small mean
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=Decimal("100.00"),
            auto_approve_max_zscore=2.5,
            mean_invoice_amount_30d=Decimal("10.00")
        )
        assert is_valid
        assert error_msg is None
        
        # Very large mean
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=Decimal("500000.00"),
            auto_approve_max_zscore=2.5,
            mean_invoice_amount_30d=Decimal("50000.00")
        )
        assert is_valid
        assert error_msg is None


class TestBaselineValidationIntegration:
    """Integration tests for baseline validation with routes."""

    def test_validation_error_messages_are_descriptive(self):
        """Test that validation error messages are descriptive."""
        service = VendorBaselineService(db=MagicMock())
        
        # Test amount error message
        is_valid, error_msg = service.validate_auto_approve_max_amount(
            Decimal("60000.00"),
            Decimal("5000.00")
        )
        assert not is_valid
        assert "60000" not in error_msg or "50000" in error_msg  # Should mention the limit
        
        # Test zscore error message
        is_valid, error_msg = service.validate_auto_approve_max_zscore(5.0)
        assert not is_valid
        assert "4.0" in error_msg

    def test_validation_with_decimal_precision(self):
        """Test validation handles decimal precision correctly."""
        service = VendorBaselineService(db=MagicMock())
        
        # Test with high precision decimals
        is_valid, error_msg = service.validate_auto_approve_max_amount(
            Decimal("50000.00"),
            Decimal("5000.00")
        )
        assert is_valid
        
        # Test with rounding edge case
        is_valid, error_msg = service.validate_auto_approve_max_amount(
            Decimal("50000.01"),
            Decimal("5000.00")
        )
        assert not is_valid

    def test_validation_deterministic(self):
        """Test that validation is deterministic."""
        service = VendorBaselineService(db=MagicMock())
        
        # Run validation twice with same inputs
        is_valid1, error_msg1 = service.validate_auto_approve_max_amount(
            Decimal("25000.00"),
            Decimal("5000.00")
        )
        is_valid2, error_msg2 = service.validate_auto_approve_max_amount(
            Decimal("25000.00"),
            Decimal("5000.00")
        )
        
        assert is_valid1 == is_valid2
        assert error_msg1 == error_msg2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
