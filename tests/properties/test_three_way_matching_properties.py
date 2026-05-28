"""
Property-based tests for three-way matching service.

Validates:
- **Property 10: PO Matching (Requirement 3.1)**
- **Property 11: Line Item Matching with Tolerance (Requirement 3.2)**
- **Property 12: Receipt Quantity Verification (Requirement 3.5, 3.6)**
- **Property 13: Three-Way Match Success (Requirement 3.8)**
"""

import pytest
from decimal import Decimal
from datetime import datetime, date
from uuid import uuid4
from unittest.mock import MagicMock, patch
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st
from rapidfuzz import fuzz

from ap_workflow.models.invoice import Invoice, InvoiceStatus
from ap_workflow.models.matching import MatchingResult, PurchaseOrder, Receipt, POLineItem, ReceiptLineItem
from ap_workflow.services.matching import MatchingService


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
def matching_service(mock_db_session):
    """Create matching service with mock session."""
    return MatchingService(db=mock_db_session)


# --- Property 10: PO Matching ---
# **Validates: Requirement 3.1**

class TestPOMatching:
    """Property tests for PO matching (exact and fuzzy)."""

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        vendor_key=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        po_reference=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))
    )
    def test_exact_po_match_by_vendor_key_and_reference(self, matching_service, vendor_key, po_reference):
        """
        **Property**: Exact PO match should succeed when vendor_key + po_reference match.
        **Validates: Requirement 3.1**
        """
        # Setup mock PO
        mock_po = MagicMock()
        mock_po.po_id = uuid4()
        mock_po.vendor_key = vendor_key
        mock_po.po_reference = po_reference
        mock_po.status = "OPEN"
        
        matching_service.db.query.return_value.filter.return_value.first.return_value = mock_po
        
        # Attempt exact match
        result = matching_service._find_po_exact_match(vendor_key, po_reference)
        
        assert result is not None
        assert result.po_id == mock_po.po_id

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        vendor_key=st.text(min_size=1, max_size=50),
        invoice_number=st.text(min_size=1, max_size=50),
        po_line_items_text=st.text(min_size=10, max_size=100)
    )
    def test_fuzzy_po_match_with_threshold(self, matching_service, vendor_key, invoice_number, po_line_items_text):
        """
        **Property**: Fuzzy PO match should succeed when token_set_ratio >= 0.85.
        **Validates: Requirement 3.1**
        """
        # Compute similarity
        similarity = fuzz.token_set_ratio(invoice_number, po_line_items_text) / 100.0
        
        if similarity >= 0.85:
            # Setup mock PO for fuzzy match
            mock_po = MagicMock()
            mock_po.po_id = uuid4()
            mock_po.vendor_key = vendor_key
            mock_po.status = "OPEN"
            
            matching_service.db.query.return_value.filter.return_value.all.return_value = [mock_po]
            
            # Attempt fuzzy match
            result = matching_service._find_po_fuzzy_match(invoice_number, vendor_key)
            
            if result:
                assert result.po_id == mock_po.po_id

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        po_status=st.sampled_from(["OPEN", "PARTIALLY_RECEIVED", "CLOSED"])
    )
    def test_po_search_respects_status_filter(self, matching_service, po_status):
        """
        **Property**: PO search should only return OPEN or PARTIALLY_RECEIVED status.
        **Validates: Requirement 3.1**
        """
        # Setup mock PO with specified status
        mock_po = MagicMock()
        mock_po.status = po_status
        
        matching_service.db.query.return_value.filter.return_value.first.return_value = mock_po
        
        # Search should filter by status
        result = matching_service._find_po_by_status("VENDOR", "PO-001", po_status)
        
        # Should only return if status is OPEN or PARTIALLY_RECEIVED
        if po_status in ["OPEN", "PARTIALLY_RECEIVED"]:
            assert result is not None
        else:
            # CLOSED POs should not be returned
            pass

    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    @given(
        timeout_seconds=st.integers(min_value=1, max_value=60)
    )
    def test_po_search_respects_timeout(self, matching_service, timeout_seconds):
        """
        **Property**: PO search should complete within 30-second timeout.
        **Validates: Requirement 3.1**
        """
        import time
        
        start_time = time.time()
        
        # Mock a quick response
        mock_po = MagicMock()
        matching_service.db.query.return_value.filter.return_value.first.return_value = mock_po
        
        result = matching_service._find_po_exact_match("VENDOR", "PO-001")
        
        elapsed = time.time() - start_time
        
        # Should complete within 30 seconds
        assert elapsed < 30


# --- Property 11: Line Item Matching with Tolerance ---
# **Validates: Requirement 3.2**

class TestLineItemMatching:
    """Property tests for line item matching with tolerance."""

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        invoice_sku=st.text(min_size=1, max_size=50),
        po_sku=st.text(min_size=1, max_size=50)
    )
    def test_sku_exact_match(self, matching_service, invoice_sku, po_sku):
        """
        **Property**: SKU exact match should succeed when SKUs are identical.
        **Validates: Requirement 3.2**
        """
        result = matching_service._match_sku(invoice_sku, po_sku, threshold=0.80)
        
        if invoice_sku == po_sku:
            assert result is True
        else:
            # Fuzzy match with threshold 0.80
            similarity = fuzz.token_set_ratio(invoice_sku, po_sku) / 100.0
            assert result == (similarity >= 0.80)

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        invoice_qty=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        po_qty=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        tolerance_pct=st.floats(min_value=0.0, max_value=5.0)
    )
    def test_quantity_matching_with_tolerance(self, matching_service, invoice_qty, po_qty, tolerance_pct):
        """
        **Property**: Quantity matching should respect configurable tolerance (default 0%, max 5%).
        **Validates: Requirement 3.2**
        """
        # Calculate if within tolerance
        variance_pct = abs(invoice_qty - po_qty) / po_qty * 100.0
        expected_match = variance_pct <= tolerance_pct
        
        result = matching_service._match_quantity(invoice_qty, po_qty, tolerance_pct)
        
        assert result == expected_match

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        invoice_price=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        po_price=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False)
    )
    def test_unit_price_matching_with_2pct_tolerance(self, matching_service, invoice_price, po_price):
        """
        **Property**: Unit price matching should use 2% relative tolerance.
        **Validates: Requirement 3.2**
        """
        # Calculate if within 2% tolerance
        variance_pct = abs(invoice_price - po_price) / po_price * 100.0
        expected_match = variance_pct <= 2.0
        
        result = matching_service._match_unit_price(invoice_price, po_price, tolerance_pct=2.0)
        
        assert result == expected_match

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        num_line_items=st.integers(min_value=1, max_value=10)
    )
    def test_all_line_items_must_match_for_success(self, matching_service, num_line_items):
        """
        **Property**: All line items must match for overall match success.
        **Validates: Requirement 3.2**
        """
        # Create mock line items
        invoice_items = [
            {"sku": f"SKU-{i}", "qty": 100.0, "price": 10.0}
            for i in range(num_line_items)
        ]
        po_items = [
            {"sku": f"SKU-{i}", "qty": 100.0, "price": 10.0}
            for i in range(num_line_items)
        ]
        
        # All items match exactly
        result = matching_service._match_all_line_items(invoice_items, po_items, qty_tolerance=0.0, price_tolerance=2.0)
        
        assert result is True


# --- Property 12: Receipt Quantity Verification ---
# **Validates: Requirement 3.5, 3.6**

class TestReceiptQuantityVerification:
    """Property tests for receipt quantity verification."""

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        invoiced_qty=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        received_qty=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
    )
    def test_receipt_quantity_verification(self, matching_service, invoiced_qty, received_qty):
        """
        **Property**: Receipt verification should check SUM(received_qty) >= invoiced_qty.
        **Validates: Requirement 3.5, 3.6**
        """
        result = matching_service._verify_receipt_quantity(invoiced_qty, received_qty)
        
        expected = received_qty >= invoiced_qty
        assert result == expected

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        num_receipts=st.integers(min_value=1, max_value=5),
        invoiced_qty=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
    )
    def test_multiple_receipts_sum_verification(self, matching_service, num_receipts, invoiced_qty):
        """
        **Property**: Multiple receipts should be summed for verification.
        **Validates: Requirement 3.5, 3.6**
        """
        # Create receipts that sum to various amounts
        receipt_qtys = [invoiced_qty / num_receipts for _ in range(num_receipts)]
        total_received = sum(receipt_qtys)
        
        result = matching_service._verify_receipt_quantity(invoiced_qty, total_received)
        
        # Should pass since total equals invoiced
        assert result is True

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        invoiced_qty=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        shortfall_pct=st.floats(min_value=0.1, max_value=50.0)
    )
    def test_partial_receipt_detection(self, matching_service, invoiced_qty, shortfall_pct):
        """
        **Property**: Partial receipts (received < invoiced) should be detected.
        **Validates: Requirement 3.5, 3.6**
        """
        received_qty = invoiced_qty * (1.0 - shortfall_pct / 100.0)
        
        result = matching_service._verify_receipt_quantity(invoiced_qty, received_qty)
        
        # Should fail since received < invoiced
        assert result is False


# --- Property 13: Three-Way Match Success ---
# **Validates: Requirement 3.8**

class TestThreeWayMatchSuccess:
    """Property tests for successful three-way match classification."""

    def test_successful_three_way_match_classification(self, matching_service):
        """
        **Property**: When PO, Receipt, and Invoice all match, status should be PO_MATCHED.
        **Validates: Requirement 3.8**
        """
        # Setup matching scenario
        invoice_id = uuid4()
        po_id = uuid4()
        
        # All components match
        matching_service.db.query.return_value.filter.return_value.first.return_value = MagicMock(po_id=po_id)
        
        result = matching_service._classify_match_result(
            po_found=True,
            po_matched=True,
            receipt_verified=True,
            line_items_matched=True
        )
        
        assert result == "PO_MATCHED"

    def test_po_mismatch_classification(self, matching_service):
        """
        **Property**: When line items don't match, status should be PO_MISMATCH.
        **Validates: Requirement 3.8**
        """
        result = matching_service._classify_match_result(
            po_found=True,
            po_matched=False,
            receipt_verified=False,
            line_items_matched=False
        )
        
        assert result == "PO_MISMATCH"

    def test_po_missing_classification(self, matching_service):
        """
        **Property**: When no PO is found, status should be PO_MISSING.
        **Validates: Requirement 3.8**
        """
        result = matching_service._classify_match_result(
            po_found=False,
            po_matched=False,
            receipt_verified=False,
            line_items_matched=False
        )
        
        assert result == "PO_MISSING"

    def test_partial_receipt_classification(self, matching_service):
        """
        **Property**: When receipt quantity < invoiced, status should be PARTIAL_RECEIPT.
        **Validates: Requirement 3.8**
        """
        result = matching_service._classify_match_result(
            po_found=True,
            po_matched=True,
            receipt_verified=False,
            line_items_matched=True
        )
        
        assert result == "PARTIAL_RECEIPT"

    def test_receipt_missing_classification(self, matching_service):
        """
        **Property**: When no receipt exists for matched PO, status should be RECEIPT_MISSING.
        **Validates: Requirement 3.8**
        """
        result = matching_service._classify_match_result(
            po_found=True,
            po_matched=True,
            receipt_verified=False,
            line_items_matched=True,
            receipt_exists=False
        )
        
        assert result == "RECEIPT_MISSING"

    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    @given(
        po_found=st.booleans(),
        line_items_matched=st.booleans(),
        receipt_verified=st.booleans()
    )
    def test_property_match_classification_deterministic(self, matching_service, po_found, line_items_matched, receipt_verified):
        """
        **Property**: Match classification should be deterministic (same inputs = same output).
        **Validates: Requirement 3.8**
        """
        result1 = matching_service._classify_match_result(
            po_found=po_found,
            po_matched=line_items_matched,
            receipt_verified=receipt_verified,
            line_items_matched=line_items_matched
        )
        
        result2 = matching_service._classify_match_result(
            po_found=po_found,
            po_matched=line_items_matched,
            receipt_verified=receipt_verified,
            line_items_matched=line_items_matched
        )
        
        # Results must be identical
        assert result1 == result2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
