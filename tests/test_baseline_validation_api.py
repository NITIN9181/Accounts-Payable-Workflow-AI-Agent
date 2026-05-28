"""Integration tests for baseline validation API endpoints."""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import MagicMock, patch

from ap_workflow.models.vendor_baseline import VendorBaseline
from ap_workflow.schemas.vendor_baseline import VendorBaselineCreate
from ap_workflow.services.vendor_baseline import VendorBaselineService


class TestBaselineValidationAPI:
    """Integration tests for baseline validation in API endpoints."""

    def test_update_baseline_with_valid_amount(self):
        """Test updating baseline with valid auto_approve_max_amount."""
        # Create mock database and service
        mock_db = MagicMock()
        
        # Create existing baseline
        existing_baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal("5000.00"),
            auto_approve_max_amount=Decimal("25000.00"),
            auto_approve_max_zscore=2.5
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = existing_baseline
        
        service = VendorBaselineService(mock_db)
        
        # Validate new amount
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=Decimal("30000.00"),
            auto_approve_max_zscore=2.5,
            mean_invoice_amount_30d=Decimal("5000.00")
        )
        
        assert is_valid
        assert error_msg is None

    def test_update_baseline_with_invalid_amount_exceeds_10x(self):
        """Test updating baseline with invalid auto_approve_max_amount (exceeds 10x)."""
        mock_db = MagicMock()
        
        existing_baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal("5000.00"),
            auto_approve_max_amount=Decimal("25000.00"),
            auto_approve_max_zscore=2.5
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = existing_baseline
        
        service = VendorBaselineService(mock_db)
        
        # Validate new amount that exceeds 10x mean
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=Decimal("60000.00"),  # > 50000 (10x mean)
            auto_approve_max_zscore=2.5,
            mean_invoice_amount_30d=Decimal("5000.00")
        )
        
        assert not is_valid
        assert "must be <= 10x mean_invoice_amount_30d" in error_msg

    def test_update_baseline_with_invalid_amount_negative(self):
        """Test updating baseline with invalid auto_approve_max_amount (negative)."""
        mock_db = MagicMock()
        
        existing_baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal("5000.00"),
            auto_approve_max_amount=Decimal("25000.00"),
            auto_approve_max_zscore=2.5
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = existing_baseline
        
        service = VendorBaselineService(mock_db)
        
        # Validate negative amount
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=Decimal("-1000.00"),
            auto_approve_max_zscore=2.5,
            mean_invoice_amount_30d=Decimal("5000.00")
        )
        
        assert not is_valid
        assert "must be >= 0" in error_msg

    def test_update_baseline_with_valid_zscore(self):
        """Test updating baseline with valid auto_approve_max_zscore."""
        mock_db = MagicMock()
        
        existing_baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal("5000.00"),
            auto_approve_max_amount=Decimal("25000.00"),
            auto_approve_max_zscore=2.5
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = existing_baseline
        
        service = VendorBaselineService(mock_db)
        
        # Validate new zscore
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=Decimal("25000.00"),
            auto_approve_max_zscore=3.0,
            mean_invoice_amount_30d=Decimal("5000.00")
        )
        
        assert is_valid
        assert error_msg is None

    def test_update_baseline_with_invalid_zscore_below_minimum(self):
        """Test updating baseline with invalid auto_approve_max_zscore (below 1.5)."""
        mock_db = MagicMock()
        
        existing_baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal("5000.00"),
            auto_approve_max_amount=Decimal("25000.00"),
            auto_approve_max_zscore=2.5
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = existing_baseline
        
        service = VendorBaselineService(mock_db)
        
        # Validate zscore below minimum
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=Decimal("25000.00"),
            auto_approve_max_zscore=1.0,
            mean_invoice_amount_30d=Decimal("5000.00")
        )
        
        assert not is_valid
        assert "must be >= 1.5" in error_msg

    def test_update_baseline_with_invalid_zscore_above_maximum(self):
        """Test updating baseline with invalid auto_approve_max_zscore (above 4.0)."""
        mock_db = MagicMock()
        
        existing_baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal("5000.00"),
            auto_approve_max_amount=Decimal("25000.00"),
            auto_approve_max_zscore=2.5
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = existing_baseline
        
        service = VendorBaselineService(mock_db)
        
        # Validate zscore above maximum
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=Decimal("25000.00"),
            auto_approve_max_zscore=5.0,
            mean_invoice_amount_30d=Decimal("5000.00")
        )
        
        assert not is_valid
        assert "must be <= 4.0" in error_msg

    def test_update_baseline_boundary_conditions(self):
        """Test updating baseline at boundary conditions."""
        mock_db = MagicMock()
        
        existing_baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal("5000.00"),
            auto_approve_max_amount=Decimal("25000.00"),
            auto_approve_max_zscore=2.5
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = existing_baseline
        
        service = VendorBaselineService(mock_db)
        
        # Test amount at exactly 10x mean
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=Decimal("50000.00"),
            auto_approve_max_zscore=2.5,
            mean_invoice_amount_30d=Decimal("5000.00")
        )
        assert is_valid
        
        # Test zscore at exactly 1.5
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=Decimal("25000.00"),
            auto_approve_max_zscore=1.5,
            mean_invoice_amount_30d=Decimal("5000.00")
        )
        assert is_valid
        
        # Test zscore at exactly 4.0
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=Decimal("25000.00"),
            auto_approve_max_zscore=4.0,
            mean_invoice_amount_30d=Decimal("5000.00")
        )
        assert is_valid

    def test_update_baseline_with_zero_amount(self):
        """Test updating baseline with zero auto_approve_max_amount (disables auto-approval)."""
        mock_db = MagicMock()
        
        existing_baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal("5000.00"),
            auto_approve_max_amount=Decimal("25000.00"),
            auto_approve_max_zscore=2.5
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = existing_baseline
        
        service = VendorBaselineService(mock_db)
        
        # Validate zero amount (should be valid)
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=Decimal("0.00"),
            auto_approve_max_zscore=2.5,
            mean_invoice_amount_30d=Decimal("5000.00")
        )
        
        assert is_valid
        assert error_msg is None

    def test_update_baseline_with_null_values(self):
        """Test updating baseline with null values (no update)."""
        mock_db = MagicMock()
        
        existing_baseline = VendorBaseline(
            vendor_key="VENDOR_001",
            mean_invoice_amount_30d=Decimal("5000.00"),
            auto_approve_max_amount=Decimal("25000.00"),
            auto_approve_max_zscore=2.5
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = existing_baseline
        
        service = VendorBaselineService(mock_db)
        
        # Validate with null values (should be valid)
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=None,
            auto_approve_max_zscore=None,
            mean_invoice_amount_30d=Decimal("5000.00")
        )
        
        assert is_valid
        assert error_msg is None

    def test_validation_error_messages_are_clear(self):
        """Test that validation error messages are clear and actionable."""
        mock_db = MagicMock()
        service = VendorBaselineService(mock_db)
        
        # Test amount error message
        is_valid, error_msg = service.validate_auto_approve_max_amount(
            Decimal("60000.00"),
            Decimal("5000.00")
        )
        assert not is_valid
        assert "auto_approve_max_amount" in error_msg
        assert "50000" in error_msg  # Should mention the limit
        
        # Test zscore error message
        is_valid, error_msg = service.validate_auto_approve_max_zscore(5.0)
        assert not is_valid
        assert "auto_approve_max_zscore" in error_msg
        assert "4.0" in error_msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
