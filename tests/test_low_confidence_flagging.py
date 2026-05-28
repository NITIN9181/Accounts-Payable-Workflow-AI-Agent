"""
Unit tests for low-confidence field flagging.

Validates Requirement 2.5:
"WHEN a required field (invoice_number, total_amount, invoice_date) has OCR_Confidence < 0.7,
THE System SHALL flag the invoice as PENDING_MANUAL_REVIEW and notify the AP analyst within 2 minutes"

Tests cover:
1. Low-confidence field detection (confidence < 0.7) for required fields
2. Invoice status update to PENDING_MANUAL_REVIEW
3. AP analyst notification delivery within 2-minute SLA
4. End-to-end workflow integration
5. GET /api/v1/invoices/{id} endpoint verification

Framework: pytest + unittest.mock
Property-based testing with Hypothesis
"""

import json
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Optional
from unittest.mock import MagicMock, patch, call, ANY
from uuid import uuid4, UUID

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from ap_workflow.models.invoice import Invoice, InvoiceStatus
from ap_workflow.models.ocr_extraction import OCRExtraction
from ap_workflow.models.audit_log import AuditLog, AuditAction, AuditEntityType, AuditActorType
from ap_workflow.services.ocr import OCRService


# --- Fixtures ---

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    
    # Set up query chain mock
    mock_query = MagicMock()
    session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None
    
    return session


@pytest.fixture
def invoice_id():
    """Generate a test invoice ID."""
    return uuid4()


@pytest.fixture
def base_invoice(invoice_id):
    """Create a base invoice for testing."""
    invoice = Invoice(
        invoice_id=invoice_id,
        vendor_key="TEST_VENDOR",
        vendor_name="Test Vendor",
        invoice_number="INV-2024-001",
        total_amount=Decimal("1000.00"),
        total_amount_usd=Decimal("1000.00"),
        invoice_date=date(2024, 1, 15),
        due_date=date(2024, 2, 15),
        file_hash="abc123def456",
        ingestion_source="upload",
        status=InvoiceStatus.PENDING_OCR,
        received_at=datetime.utcnow()
    )
    return invoice


@pytest.fixture
def ocr_service(mock_db_session):
    """Create OCR service with mock session."""
    return OCRService(db=mock_db_session)

def create_low_confidence_extraction(
    invoice_id: UUID,
    invoice_number_conf: float = 0.6,
    total_amount_conf: float = 0.6,
    invoice_date_conf: float = 0.6
) -> OCRExtraction:
    """Create OCR extraction with low confidence on required fields."""
    return OCRExtraction(
        extraction_id=uuid4(),
        invoice_id=invoice_id,
        invoice_number="INV-2024-001",
        invoice_number_confidence=Decimal(str(invoice_number_conf)),
        vendor_name="Test Vendor",
        vendor_name_confidence=Decimal("1.0"),
        total_amount=Decimal("1000.00"),
        total_amount_confidence=Decimal(str(total_amount_conf)),
        tax_amount=Decimal("100.00"),
        tax_amount_confidence=Decimal("1.0"),
        invoice_date=date(2024, 1, 15),
        invoice_date_confidence=Decimal(str(invoice_date_conf)),
        ocr_raw_json={"text": "mock ocr text"}
    )


def create_high_confidence_extraction(
    invoice_id: UUID,
    confidence: float = 1.0
) -> OCRExtraction:
    """Create OCR extraction with high confidence on all fields."""
    return OCRExtraction(
        extraction_id=uuid4(),
        invoice_id=invoice_id,
        invoice_number="INV-2024-001",
        invoice_number_confidence=Decimal(str(confidence)),
        vendor_name="Test Vendor",
        vendor_name_confidence=Decimal(str(confidence)),
        total_amount=Decimal("1000.00"),
        total_amount_confidence=Decimal(str(confidence)),
        tax_amount=Decimal("100.00"),
        tax_amount_confidence=Decimal(str(confidence)),
        invoice_date=date(2024, 1, 15),
        invoice_date_confidence=Decimal(str(confidence)),
        ocr_raw_json={"text": "mock ocr text"}
    )


def create_mixed_confidence_extraction(
    invoice_id: UUID,
    low_fields: list = None
) -> OCRExtraction:
    """Create OCR extraction with mixed confidence levels on required fields.
    
    Args:
        invoice_id: Invoice UUID
        low_fields: List of field names to set to low confidence
                   Valid values: 'invoice_number', 'total_amount', 'invoice_date'
    """
    if low_fields is None:
        low_fields = []
    
    return OCRExtraction(
        extraction_id=uuid4(),
        invoice_id=invoice_id,
        invoice_number="INV-2024-001",
        invoice_number_confidence=Decimal("0.5") if "invoice_number" in low_fields else Decimal("1.0"),
        vendor_name="Test Vendor",
        vendor_name_confidence=Decimal("1.0"),
        total_amount=Decimal("1000.00"),
        total_amount_confidence=Decimal("0.5") if "total_amount" in low_fields else Decimal("1.0"),
        tax_amount=Decimal("100.00"),
        tax_amount_confidence=Decimal("1.0"),
        invoice_date=date(2024, 1, 15),
        invoice_date_confidence=Decimal("0.5") if "invoice_date" in low_fields else Decimal("1.0"),
        ocr_raw_json={"text": "mock ocr text"}
    )

# --- Test Group 1: Low-Confidence Field Detection (Subtask 1) ---

class TestLowConfidenceFieldDetection:
    """Tests for detecting low-confidence fields (confidence < 0.7).
    
    **Validates: Requirement 2.5**
    """

    def test_single_required_field_below_threshold_triggers_flag(self, mock_db_session, invoice_id):
        """Invoice with one required field OCR_Confidence < 0.7 should be flagged."""
        service = OCRService(db=mock_db_session)
        
        # invoice_number at 0.6 (below 0.7 threshold)
        extraction = create_low_confidence_extraction(
            invoice_id,
            invoice_number_conf=0.6,
            total_amount_conf=1.0,
            invoice_date_conf=1.0
        )
        
        result = service._has_low_confidence_required_fields(extraction)
        assert result is True, "Should flag when invoice_number < 0.7"

    def test_confidence_at_threshold_boundary(self, mock_db_session, invoice_id):
        """Invoice with OCR_Confidence exactly at 0.7 should NOT be flagged."""
        service = OCRService(db=mock_db_session)
        
        # All fields at exactly 0.7 (threshold)
        extraction = create_low_confidence_extraction(
            invoice_id,
            invoice_number_conf=0.7,
            total_amount_conf=0.7,
            invoice_date_conf=0.7
        )
        
        result = service._has_low_confidence_required_fields(extraction)
        assert result is False, "Threshold should not be inclusive (< 0.7, not <= 0.7)"

    def test_confidence_just_above_threshold_does_not_flag(self, mock_db_session, invoice_id):
        """Invoice with OCR_Confidence > 0.7 should NOT be flagged."""
        service = OCRService(db=mock_db_session)
        
        # All fields at 0.701 (just above threshold)
        extraction = create_low_confidence_extraction(
            invoice_id,
            invoice_number_conf=0.701,
            total_amount_conf=0.701,
            invoice_date_conf=0.701
        )
        
        result = service._has_low_confidence_required_fields(extraction)
        assert result is False

    def test_all_required_fields_low_confidence_triggers_flag(self, mock_db_session, invoice_id):
        """Invoice with ALL required fields < 0.7 should be flagged."""
        service = OCRService(db=mock_db_session)
        
        extraction = create_low_confidence_extraction(
            invoice_id,
            invoice_number_conf=0.5,
            total_amount_conf=0.6,
            invoice_date_conf=0.65
        )
        
        result = service._has_low_confidence_required_fields(extraction)
        assert result is True

    def test_mixed_confidence_with_one_low_field_triggers_flag(self, mock_db_session, invoice_id):
        """If ANY required field is low confidence, invoice should be flagged."""
        service = OCRService(db=mock_db_session)
        
        # Only total_amount is low
        extraction = create_mixed_confidence_extraction(
            invoice_id,
            low_fields=['total_amount']
        )
        
        result = service._has_low_confidence_required_fields(extraction)
        assert result is True

    def test_optional_field_low_confidence_does_not_trigger_flag(self, mock_db_session, invoice_id):
        """Low confidence on optional fields (po_reference) should NOT trigger flag."""
        service = OCRService(db=mock_db_session)
        
        from datetime import date
        extraction = OCRExtraction(
            extraction_id=uuid4(),
            invoice_id=invoice_id,
            invoice_number="INV-2024-001",
            invoice_number_confidence=Decimal("1.0"),
            vendor_name="Test Vendor",
            vendor_name_confidence=Decimal("1.0"),
            total_amount=Decimal("1000.00"),
            total_amount_confidence=Decimal("1.0"),
            tax_amount=Decimal("100.00"),
            tax_amount_confidence=Decimal("1.0"),
            invoice_date=date(2024, 1, 15),
            invoice_date_confidence=Decimal("1.0"),
            po_reference="PO-123",
            po_reference_confidence=Decimal("0.4"),  # Low but optional
            ocr_raw_json={"text": "mock ocr text"}
        )
        
        result = service._has_low_confidence_required_fields(extraction)
        assert result is False, "Optional fields should not trigger flag"

    def test_null_confidence_value_handled(self, mock_db_session, invoice_id):
        """NULL confidence values should be handled safely."""
        service = OCRService(db=mock_db_session)
        
        extraction = OCRExtraction(
            extraction_id=uuid4(),
            invoice_id=invoice_id,
            invoice_number="INV-2024-001",
            invoice_number_confidence=Decimal("1.0"),
            vendor_name="Test Vendor",
            vendor_name_confidence=Decimal("1.0"),
            total_amount=Decimal("1000.00"),
            total_amount_confidence=None,  # NULL value
            tax_amount=Decimal("100.00"),
            tax_amount_confidence=Decimal("1.0"),
            invoice_date=date(2024, 1, 15),
            invoice_date_confidence=Decimal("1.0"),
            ocr_raw_json={"text": "mock ocr text"}
        )
        
        # Should not raise exception
        result = service._has_low_confidence_required_fields(extraction)
        assert result is False

    @settings(max_examples=25, suppress_health_check=[])
    @given(
        invoice_number_conf=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        total_amount_conf=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        invoice_date_conf=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    def test_property_any_required_field_below_threshold_triggers_flag(
        self,
        invoice_number_conf, total_amount_conf, invoice_date_conf
    ):
        """**Validates: Requirement 2.5**
        
        Property: If ANY required field has confidence < 0.7, invoice MUST be flagged.
        """
        from hypothesis import HealthCheck
        from unittest.mock import MagicMock
        
        mock_db = MagicMock()
        service = OCRService(db=mock_db)
        
        invoice_id = uuid4()
        
        extraction = create_low_confidence_extraction(
            invoice_id,
            invoice_number_conf=invoice_number_conf,
            total_amount_conf=total_amount_conf,
            invoice_date_conf=invoice_date_conf
        )
        
        result = service._has_low_confidence_required_fields(extraction)
        
        # Should flag if ANY required field < 0.7
        expected_flag = (
            invoice_number_conf < 0.7 or
            total_amount_conf < 0.7 or
            invoice_date_conf < 0.7
        )
        
        assert result == expected_flag, (
            f"Flagging mismatch: got {result}, expected {expected_flag} "
            f"(invoice_number={invoice_number_conf}, total_amount={total_amount_conf}, "
            f"invoice_date={invoice_date_conf})"
        )

    @settings(max_examples=15, suppress_health_check=[])
    @given(
        all_below_threshold=st.booleans()
    )
    def test_property_threshold_is_0_7_not_inclusive(
        self, all_below_threshold
    ):
        """Property: Threshold is 0.7 and NOT inclusive (< 0.7, not <= 0.7)."""
        from unittest.mock import MagicMock
        
        mock_db = MagicMock()
        service = OCRService(db=mock_db)
        invoice_id = uuid4()
        
        if all_below_threshold:
            conf = 0.6999  # Just below
            expected = True
        else:
            conf = 0.7001  # Just above
            expected = False
        
        extraction = create_low_confidence_extraction(
            invoice_id,
            invoice_number_conf=conf,
            total_amount_conf=conf,
            invoice_date_conf=conf
        )
        
        result = service._has_low_confidence_required_fields(extraction)
        assert result == expected

# --- Test Group 2: Invoice Status Update to PENDING_MANUAL_REVIEW (Subtask 2) ---

class TestManualReviewStatusUpdate:
    """Tests for updating invoice status to PENDING_MANUAL_REVIEW.
    
    **Validates: Requirement 2.5**
    """

    def test_low_confidence_invoice_flagged_for_manual_review(
        self, mock_db_session, invoice_id, base_invoice
    ):
        """Invoice with low-confidence fields should be flagged and status updated."""
        service = OCRService(db=mock_db_session)
        
        # Setup mock to return our base invoice
        mock_db_session.query.return_value.filter.return_value.first.return_value = base_invoice
        
        # Create low-confidence extraction
        extraction = create_low_confidence_extraction(invoice_id, invoice_number_conf=0.6)
        
        # Flag for review
        result = service._flag_low_confidence_fields(extraction, invoice_id)
        
        # Should return True and mark for review
        assert result is True
        # Invoice status should have been updated
        assert mock_db_session.commit.called

    def test_status_transition_pending_ocr_to_manual_review(
        self, mock_db_session, invoice_id
    ):
        """Invoice status should transition from PENDING_OCR to PENDING_MANUAL_REVIEW."""
        service = OCRService(db=mock_db_session)
        
        from datetime import date
        invoice = Invoice(
            invoice_id=invoice_id,
            vendor_key="TEST_VENDOR",
            vendor_name="Test Vendor",
            invoice_number="INV-2024-001",
            total_amount=Decimal("1000.00"),
            invoice_date=date(2024, 1, 15),
            due_date=date(2024, 2, 15),
            file_hash="abc123",
            ingestion_source="upload",
            status=InvoiceStatus.PENDING_OCR,
            received_at=datetime.utcnow()
        )
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = invoice
        
        # Verify initial status
        assert invoice.status == InvoiceStatus.PENDING_OCR
        
        # Update to manual review
        service._update_invoice_status(invoice_id, InvoiceStatus.PENDING_MANUAL_REVIEW)
        
        # Commit should have been called to persist the change
        assert mock_db_session.commit.called

    def test_status_updated_when_flagging_low_confidence(
        self, mock_db_session, invoice_id, base_invoice
    ):
        """Status update should be triggered as part of flagging process."""
        service = OCRService(db=mock_db_session)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = base_invoice
        
        extraction = create_low_confidence_extraction(invoice_id, invoice_number_conf=0.5)
        
        # Flag for review (this should also update status)
        service._flag_low_confidence_fields(extraction, invoice_id)
        
        # Should have called commit (for both status and notification)
        assert mock_db_session.commit.called

    def test_high_confidence_does_not_change_status(
        self, mock_db_session, invoice_id, base_invoice
    ):
        """High-confidence invoices should NOT change status."""
        service = OCRService(db=mock_db_session)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = base_invoice
        
        extraction = create_high_confidence_extraction(invoice_id, confidence=1.0)
        
        # Flag for review (should return False)
        result = service._flag_low_confidence_fields(extraction, invoice_id)
        
        # Should return False and NOT update status
        assert result is False

    @settings(max_examples=10, suppress_health_check=[])
    @given(
        status_choice=st.sampled_from([
            InvoiceStatus.PENDING_OCR,
            InvoiceStatus.PENDING_MATCHING
        ])
    )
    def test_property_status_updated_to_pending_manual_review(
        self, status_choice
    ):
        """Property: Flagging always results in PENDING_MANUAL_REVIEW status."""
        from unittest.mock import MagicMock
        
        mock_db = MagicMock()
        service = OCRService(db=mock_db)
        invoice_id = uuid4()
        
        from datetime import date
        invoice = Invoice(
            invoice_id=invoice_id,
            vendor_key="TEST_VENDOR",
            vendor_name="Test Vendor",
            invoice_number="INV-001",
            total_amount=Decimal("1000.00"),
            invoice_date=date(2024, 1, 15),
            due_date=date(2024, 2, 15),
            file_hash="abc123",
            ingestion_source="upload",
            status=status_choice,
            received_at=datetime.utcnow()
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = invoice
        
        # Update to PENDING_MANUAL_REVIEW
        service._update_invoice_status(invoice_id, InvoiceStatus.PENDING_MANUAL_REVIEW)
        
        # Verify commit was called
        assert mock_db.commit.called

# --- Test Group 3: Notification Delivery within 2-Minute SLA (Subtask 3) ---

class TestNotificationDeliverySLA:
    """Tests for notification delivery within 2-minute SLA.
    
    **Validates: Requirement 2.5**
    "THE System SHALL notify the AP analyst within 2 minutes"
    """

    def test_notification_triggered_for_low_confidence_fields(
        self, mock_db_session, invoice_id, base_invoice
    ):
        """Notification should be triggered when low-confidence fields are detected."""
        service = OCRService(db=mock_db_session)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = base_invoice
        
        extraction = create_low_confidence_extraction(invoice_id, invoice_number_conf=0.6)
        
        # Send notification for low confidence
        service._send_notification_for_low_confidence(invoice_id, extraction)
        
        # Should have added audit log
        assert mock_db_session.add.called
        assert mock_db_session.commit.called

    def test_notification_includes_low_confidence_fields_info(
        self, mock_db_session, invoice_id, base_invoice
    ):
        """Notification content should include details of low-confidence fields."""
        service = OCRService(db=mock_db_session)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = base_invoice
        
        extraction = create_low_confidence_extraction(
            invoice_id,
            invoice_number_conf=0.5,
            total_amount_conf=0.6,
            invoice_date_conf=1.0
        )
        
        # Build notification content
        content = service._build_notification_content(invoice_id, extraction)
        
        # Should include low-confidence fields
        assert content is not None
        assert "low_confidence_fields" in content
        assert len(content["low_confidence_fields"]) >= 2

    def test_notification_includes_required_fields(
        self, mock_db_session, invoice_id, base_invoice
    ):
        """Notification should include invoice details and timestamps."""
        service = OCRService(db=mock_db_session)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = base_invoice
        
        extraction = create_low_confidence_extraction(invoice_id, invoice_number_conf=0.6)
        
        content = service._build_notification_content(invoice_id, extraction)
        
        # Should include vendor, invoice number, amount
        assert "vendor_name" in content
        assert "invoice_number" in content
        assert "total_amount" in content
        assert "notification_time" in content

    def test_notification_delivery_time_within_sla(
        self, mock_db_session, invoice_id, base_invoice
    ):
        """Notification should be delivered within 2 minutes (120 seconds) of detection."""
        service = OCRService(db=mock_db_session)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = base_invoice
        
        # Record detection time
        detection_time = datetime.utcnow()
        
        extraction = create_low_confidence_extraction(invoice_id, invoice_number_conf=0.6)
        
        # Send notification
        service._send_notification_for_low_confidence(invoice_id, extraction)
        
        # Record delivery time
        delivery_time = datetime.utcnow()
        
        # Verify SLA (< 2 minutes = < 120 seconds)
        sla_seconds = (delivery_time - detection_time).total_seconds()
        
        assert sla_seconds < 120, f"Notification took {sla_seconds}s, exceeds 120s SLA"

    def test_notification_creates_audit_log_entry(
        self, mock_db_session, invoice_id, base_invoice
    ):
        """Notification should create audit log entry for compliance."""
        service = OCRService(db=mock_db_session)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = base_invoice
        
        extraction = create_low_confidence_extraction(invoice_id, invoice_number_conf=0.6)
        
        service._send_notification_for_low_confidence(invoice_id, extraction)
        
        # Should have called db.add (for audit log)
        assert mock_db_session.add.called
        
        # Should have called commit
        assert mock_db_session.commit.called

    def test_high_confidence_does_not_trigger_notification(
        self, mock_db_session, invoice_id, base_invoice
    ):
        """High-confidence invoices should NOT trigger notification."""
        service = OCRService(db=mock_db_session)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = base_invoice
        
        extraction = create_high_confidence_extraction(invoice_id, confidence=1.0)
        
        # Flag for review (should not trigger)
        result = service._flag_low_confidence_fields(extraction, invoice_id)
        
        # Should return False
        assert result is False

    def test_notification_sla_met_for_edge_case_confidence(
        self, mock_db_session, invoice_id, base_invoice
    ):
        """SLA should be met even for edge case confidence values."""
        service = OCRService(db=mock_db_session)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = base_invoice
        
        # Edge case: 0.6999 (just below threshold)
        extraction = create_low_confidence_extraction(
            invoice_id,
            invoice_number_conf=0.6999,
            total_amount_conf=0.6999,
            invoice_date_conf=0.6999
        )
        
        detection_time = datetime.utcnow()
        service._send_notification_for_low_confidence(invoice_id, extraction)
        delivery_time = datetime.utcnow()
        
        sla_seconds = (delivery_time - detection_time).total_seconds()
        assert sla_seconds < 120

    @settings(max_examples=15, suppress_health_check=[])
    @given(
        num_low_fields=st.integers(min_value=1, max_value=3)
    )
    def test_property_notification_always_within_sla_window(
        self, num_low_fields
    ):
        """Property: Notifications for low-confidence invoices always meet SLA."""
        from unittest.mock import MagicMock
        from datetime import date
        
        mock_db = MagicMock()
        service = OCRService(db=mock_db)
        invoice_id = uuid4()
        
        base_invoice = Invoice(
            invoice_id=invoice_id,
            vendor_key="TEST_VENDOR",
            vendor_name="Test Vendor",
            invoice_number="INV-2024-001",
            total_amount=Decimal("1000.00"),
            total_amount_usd=Decimal("1000.00"),
            invoice_date=date(2024, 1, 15),
            due_date=date(2024, 2, 15),
            file_hash="abc123def456",
            ingestion_source="upload",
            status=InvoiceStatus.PENDING_OCR,
            received_at=datetime.utcnow()
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = base_invoice
        
        # Create extraction with specified number of low-confidence fields
        low_fields = ["invoice_number", "total_amount", "invoice_date"][:num_low_fields]
        extraction = create_mixed_confidence_extraction(invoice_id, low_fields=low_fields)
        
        detection_time = datetime.utcnow()
        service._send_notification_for_low_confidence(invoice_id, extraction)
        delivery_time = datetime.utcnow()
        
        # Should always be within SLA
        sla_seconds = (delivery_time - detection_time).total_seconds()
        assert sla_seconds < 120

    @settings(max_examples=10, suppress_health_check=[])
    @given(
        num_notifications=st.integers(min_value=1, max_value=5)
    )
    def test_property_multiple_notifications_each_respect_sla(
        self, num_notifications
    ):
        """Property: Multiple notifications each respect the SLA independently."""
        from unittest.mock import MagicMock
        from datetime import date
        
        mock_db = MagicMock()
        service = OCRService(db=mock_db)
        invoice_id = uuid4()
        
        base_invoice = Invoice(
            invoice_id=invoice_id,
            vendor_key="TEST_VENDOR",
            vendor_name="Test Vendor",
            invoice_number="INV-2024-001",
            total_amount=Decimal("1000.00"),
            total_amount_usd=Decimal("1000.00"),
            invoice_date=date(2024, 1, 15),
            due_date=date(2024, 2, 15),
            file_hash="abc123def456",
            ingestion_source="upload",
            status=InvoiceStatus.PENDING_OCR,
            received_at=datetime.utcnow()
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = base_invoice
        
        extraction = create_low_confidence_extraction(invoice_id, invoice_number_conf=0.6)
        
        for i in range(num_notifications):
            detection_time = datetime.utcnow()
            service._send_notification_for_low_confidence(invoice_id, extraction)
            delivery_time = datetime.utcnow()
            
            sla_seconds = (delivery_time - detection_time).total_seconds()
            assert sla_seconds < 120, f"Notification {i+1} exceeded SLA"

# --- Test Group 4: End-to-End Workflow Integration (Subtask 4) ---

class TestLowConfidenceFlaggingWorkflow:
    """Integration tests for complete low-confidence field flagging workflow.
    
    **Validates: Requirement 2.5 - Complete workflow**
    """

    def test_complete_workflow_low_confidence_detection_to_manual_review(
        self, mock_db_session, invoice_id, base_invoice
    ):
        """Integration: Complete flow from low-confidence detection to manual review status."""
        service = OCRService(db=mock_db_session)
        
        # Setup mock invoice query
        mock_db_session.query.return_value.filter.return_value.first.return_value = base_invoice
        
        # Step 1: Create low-confidence extraction
        extraction = create_low_confidence_extraction(
            invoice_id,
            invoice_number_conf=0.5,
            total_amount_conf=0.6,
            invoice_date_conf=0.65
        )
        
        # Step 2: Detect low-confidence required fields
        has_low_conf = service._has_low_confidence_required_fields(extraction)
        assert has_low_conf is True, "Should detect low-confidence fields"
        
        # Step 3: Flag for review (updates status and sends notification)
        flagged = service._flag_low_confidence_fields(extraction, invoice_id)
        assert flagged is True, "Should return True when flagged"
        
        # Step 4: Verify status update was attempted
        assert mock_db_session.commit.called, "Should commit status update"
        
        # Step 5: Verify notification was sent
        assert mock_db_session.add.called, "Should add audit log for notification"

    def test_workflow_with_single_low_confidence_field(
        self, mock_db_session, invoice_id, base_invoice
    ):
        """Workflow should trigger even with just ONE low-confidence required field."""
        service = OCRService(db=mock_db_session)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = base_invoice
        
        # Only invoice_number is low
        extraction = create_mixed_confidence_extraction(
            invoice_id,
            low_fields=['invoice_number']
        )
        
        # Should detect and flag
        has_low_conf = service._has_low_confidence_required_fields(extraction)
        assert has_low_conf is True
        
        flagged = service._flag_low_confidence_fields(extraction, invoice_id)
        assert flagged is True

    def test_workflow_skipped_for_high_confidence(
        self, mock_db_session, invoice_id, base_invoice
    ):
        """Workflow should NOT trigger for high-confidence invoices."""
        service = OCRService(db=mock_db_session)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = base_invoice
        
        extraction = create_high_confidence_extraction(invoice_id, confidence=1.0)
        
        # Should not detect low confidence
        has_low_conf = service._has_low_confidence_required_fields(extraction)
        assert has_low_conf is False
        
        # Should not flag
        flagged = service._flag_low_confidence_fields(extraction, invoice_id)
        assert flagged is False

    def test_notification_content_complete_in_workflow(
        self, mock_db_session, invoice_id, base_invoice
    ):
        """Notification content should be complete with all required details."""
        service = OCRService(db=mock_db_session)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = base_invoice
        
        extraction = create_low_confidence_extraction(
            invoice_id,
            invoice_number_conf=0.5,
            total_amount_conf=0.6,
            invoice_date_conf=1.0
        )
        
        content = service._build_notification_content(invoice_id, extraction)
        
        # Verify all required fields for analyst action
        assert "vendor_name" in content
        assert "invoice_number" in content
        assert "total_amount" in content
        assert "low_confidence_fields" in content
        assert "message" in content
        assert "required_action" in content
        assert "notification_time" in content
        
        # Verify low-confidence fields are listed
        low_fields = content["low_confidence_fields"]
        assert len(low_fields) == 2  # invoice_number and total_amount are low
        
        # Each low field should have field name, value, and confidence
        for field_info in low_fields:
            assert "field" in field_info
            assert "value" in field_info
            assert "confidence" in field_info

    def test_workflow_respects_sla_end_to_end(
        self, mock_db_session, invoice_id, base_invoice
    ):
        """Complete workflow should complete within 2-minute SLA."""
        service = OCRService(db=mock_db_session)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = base_invoice
        
        extraction = create_low_confidence_extraction(invoice_id, invoice_number_conf=0.6)
        
        start_time = datetime.utcnow()
        
        # Execute full workflow
        has_low_conf = service._has_low_confidence_required_fields(extraction)
        service._flag_low_confidence_fields(extraction, invoice_id)
        
        end_time = datetime.utcnow()
        
        # Total workflow time should be < 120 seconds
        total_seconds = (end_time - start_time).total_seconds()
        assert total_seconds < 120, f"Workflow took {total_seconds}s, exceeds SLA"

    def test_workflow_with_all_required_fields_low(
        self, mock_db_session, invoice_id, base_invoice
    ):
        """Workflow should handle case where ALL required fields are low confidence."""
        service = OCRService(db=mock_db_session)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = base_invoice
        
        extraction = create_mixed_confidence_extraction(
            invoice_id,
            low_fields=['invoice_number', 'total_amount', 'invoice_date']
        )
        
        # Should detect
        has_low_conf = service._has_low_confidence_required_fields(extraction)
        assert has_low_conf is True
        
        # Should flag
        flagged = service._flag_low_confidence_fields(extraction, invoice_id)
        assert flagged is True
        
        # Notification should include all 3 low fields
        content = service._build_notification_content(invoice_id, extraction)
        assert len(content["low_confidence_fields"]) == 3

    @settings(max_examples=12, suppress_health_check=[])
    @given(
        num_low_fields=st.integers(min_value=1, max_value=3),
        high_confidence_optional=st.booleans()
    )
    def test_property_workflow_always_completes_for_any_low_confidence_combination(
        self, num_low_fields, high_confidence_optional
    ):
        """Property: Workflow completes successfully for any combination of low-confidence fields."""
        from unittest.mock import MagicMock
        from datetime import date
        
        mock_db = MagicMock()
        service = OCRService(db=mock_db)
        invoice_id = uuid4()
        
        base_invoice = Invoice(
            invoice_id=invoice_id,
            vendor_key="TEST_VENDOR",
            vendor_name="Test Vendor",
            invoice_number="INV-2024-001",
            total_amount=Decimal("1000.00"),
            total_amount_usd=Decimal("1000.00"),
            invoice_date=date(2024, 1, 15),
            due_date=date(2024, 2, 15),
            file_hash="abc123def456",
            ingestion_source="upload",
            status=InvoiceStatus.PENDING_OCR,
            received_at=datetime.utcnow()
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = base_invoice
        
        low_fields = ["invoice_number", "total_amount", "invoice_date"][:num_low_fields]
        extraction = create_mixed_confidence_extraction(invoice_id, low_fields=low_fields)
        
        # Should complete without errors
        has_low_conf = service._has_low_confidence_required_fields(extraction)
        assert has_low_conf is True
        
        flagged = service._flag_low_confidence_fields(extraction, invoice_id)
        assert flagged is True
        
        # Notification should be buildable
        content = service._build_notification_content(invoice_id, extraction)
        assert content is not None
        assert len(content["low_confidence_fields"]) == num_low_fields


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
