"""
Property-based tests for data model validation.

Validates:
- **Property 2: Manual Entry Field Validation (Requirement 1.4)**
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st
from pydantic import ValidationError

from ap_workflow.schemas.invoice import InvoiceCreate, InvoiceLineItemCreate
from ap_workflow.schemas.ocr_extraction import OCRExtractionCreate
from ap_workflow.schemas.exception import InvoiceExceptionCreate
from ap_workflow.schemas.approval import ApprovalCreate
from ap_workflow.schemas.audit_log import AuditLogResponse


# --- Strategies ---

def alphanumeric_invoice_number():
    """Generate valid alphanumeric invoice numbers."""
    return st.text(
        min_size=1,
        max_size=50,
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    )


def valid_vendor_name():
    """Generate valid vendor names."""
    return st.text(
        min_size=1,
        max_size=100,
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -.,&'"
    )


def valid_amount():
    """Generate valid positive amounts <= 999,999.99."""
    return st.decimals(
        min_value=Decimal('0.01'),
        max_value=Decimal('999999.99'),
        places=2,
        allow_nan=False,
        allow_infinity=False
    )


def valid_date_pair():
    """Generate valid invoice_date and due_date pairs."""
    return st.tuples(
        st.dates(
            min_value=date(2020, 1, 1),
            max_value=date(2030, 12, 31)
        ),
        st.dates(
            min_value=date(2020, 1, 1),
            max_value=date(2030, 12, 31)
        )
    ).filter(lambda pair: pair[1] >= pair[0])


# --- Property 2: Manual Entry Field Validation ---
# **Validates: Requirement 1.4**
# Property: WHEN an AP analyst manually enters invoice details via the web form, 
# THE Manual_Entry_Form SHALL validate all required fields:
# - invoice_number: alphanumeric 1-50 chars
# - vendor_name: 1-100 chars
# - total_amount: positive decimal ≤ 999,999.99
# - invoice_date: valid ISO 8601 date
# - due_date: valid ISO 8601 date ≥ invoice_date

class TestManualEntryFieldValidation:
    """Property tests for manual entry field validation."""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        vendor_key=st.text(min_size=1, max_size=100),
        invoice_number=alphanumeric_invoice_number(),
        vendor_name=valid_vendor_name(),
        total_amount=valid_amount(),
        dates=valid_date_pair()
    )
    def test_valid_manual_entry_fields_accepted(
        self,
        vendor_key,
        invoice_number,
        vendor_name,
        total_amount,
        dates
    ):
        """
        **Property**: Valid manual entry fields should be accepted.
        **Validates: Requirement 1.4**
        
        When all required fields are valid:
        - invoice_number is alphanumeric 1-50 chars
        - vendor_name is 1-100 chars
        - total_amount is positive decimal ≤ 999,999.99
        - invoice_date is valid ISO 8601 date
        - due_date is valid ISO 8601 date ≥ invoice_date
        
        Then the invoice should be created successfully.
        """
        invoice_date, due_date = dates
        
        # Create invoice with valid fields
        invoice = InvoiceCreate(
            vendor_key=vendor_key,
            vendor_name=vendor_name,
            invoice_number=invoice_number,
            total_amount=total_amount,
            invoice_date=invoice_date,
            due_date=due_date
        )
        
        # Verify all fields are set correctly
        assert invoice.vendor_key == vendor_key
        assert invoice.vendor_name == vendor_name
        assert invoice.invoice_number == invoice_number
        assert invoice.total_amount == total_amount
        assert invoice.invoice_date == invoice_date
        assert invoice.due_date == due_date

    @settings(max_examples=50)
    @given(
        invoice_number=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                blacklist_categories=('Lu', 'Ll', 'Nd'),
                blacklist_characters='-_'
            )
        )
    )
    def test_invalid_invoice_number_rejected(self, invoice_number):
        """
        **Property**: Invalid invoice numbers (non-alphanumeric) should be rejected.
        **Validates: Requirement 1.4**
        
        When invoice_number contains non-alphanumeric characters (except - and _),
        Then validation should fail.
        """
        assume(len(invoice_number) > 0)  # Ensure we have a string
        
        with pytest.raises(ValidationError) as exc_info:
            InvoiceCreate(
                vendor_key="TEST",
                vendor_name="Test Vendor",
                invoice_number=invoice_number,
                total_amount=Decimal('1000.00'),
                invoice_date=date(2024, 1, 1),
                due_date=date(2024, 2, 1)
            )
        
        # Verify the error is about invoice_number
        errors = exc_info.value.errors()
        assert any('invoice_number' in str(e) for e in errors)

    @settings(max_examples=50)
    @given(
        invoice_number=st.text(min_size=51, max_size=100)
    )
    def test_invoice_number_too_long_rejected(self, invoice_number):
        """
        **Property**: Invoice numbers longer than 50 chars should be rejected.
        **Validates: Requirement 1.4**
        
        When invoice_number exceeds 50 characters,
        Then validation should fail.
        """
        with pytest.raises(ValidationError) as exc_info:
            InvoiceCreate(
                vendor_key="TEST",
                vendor_name="Test Vendor",
                invoice_number=invoice_number,
                total_amount=Decimal('1000.00'),
                invoice_date=date(2024, 1, 1),
                due_date=date(2024, 2, 1)
            )
        
        errors = exc_info.value.errors()
        assert any('invoice_number' in str(e) for e in errors)

    @settings(max_examples=50)
    @given(
        vendor_name=st.text(min_size=101, max_size=200)
    )
    def test_vendor_name_too_long_rejected(self, vendor_name):
        """
        **Property**: Vendor names longer than 100 chars should be rejected.
        **Validates: Requirement 1.4**
        
        When vendor_name exceeds 100 characters,
        Then validation should fail.
        """
        with pytest.raises(ValidationError) as exc_info:
            InvoiceCreate(
                vendor_key="TEST",
                vendor_name=vendor_name,
                invoice_number="INV-001",
                total_amount=Decimal('1000.00'),
                invoice_date=date(2024, 1, 1),
                due_date=date(2024, 2, 1)
            )
        
        errors = exc_info.value.errors()
        assert any('vendor_name' in str(e) for e in errors)

    @settings(max_examples=50)
    @given(
        total_amount=st.decimals(
            min_value=Decimal('999999.99'),
            max_value=Decimal('9999999.99'),
            places=2,
            allow_nan=False,
            allow_infinity=False
        )
    )
    def test_total_amount_exceeds_max_rejected(self, total_amount):
        """
        **Property**: Total amounts exceeding 999,999.99 should be rejected.
        **Validates: Requirement 1.4**
        
        When total_amount exceeds 999,999.99,
        Then validation should fail.
        """
        assume(total_amount > Decimal('999999.99'))
        
        with pytest.raises(ValidationError) as exc_info:
            InvoiceCreate(
                vendor_key="TEST",
                vendor_name="Test Vendor",
                invoice_number="INV-001",
                total_amount=total_amount,
                invoice_date=date(2024, 1, 1),
                due_date=date(2024, 2, 1)
            )
        
        errors = exc_info.value.errors()
        assert any('total_amount' in str(e) for e in errors)

    @settings(max_examples=50)
    @given(
        total_amount=st.decimals(
            min_value=Decimal('-9999.99'),
            max_value=Decimal('0.00'),
            places=2,
            allow_nan=False,
            allow_infinity=False
        )
    )
    def test_negative_total_amount_rejected(self, total_amount):
        """
        **Property**: Negative or zero total amounts should be rejected.
        **Validates: Requirement 1.4**
        
        When total_amount is <= 0,
        Then validation should fail.
        """
        assume(total_amount <= 0)
        
        with pytest.raises(ValidationError) as exc_info:
            InvoiceCreate(
                vendor_key="TEST",
                vendor_name="Test Vendor",
                invoice_number="INV-001",
                total_amount=total_amount,
                invoice_date=date(2024, 1, 1),
                due_date=date(2024, 2, 1)
            )
        
        errors = exc_info.value.errors()
        assert any('total_amount' in str(e) for e in errors)

    @settings(max_examples=50)
    @given(
        invoice_date=st.dates(
            min_value=date(2020, 1, 1),
            max_value=date(2030, 12, 31)
        ),
        due_date=st.dates(
            min_value=date(2020, 1, 1),
            max_value=date(2030, 12, 31)
        )
    )
    def test_due_date_before_invoice_date_rejected(self, invoice_date, due_date):
        """
        **Property**: Due dates before invoice dates should be rejected.
        **Validates: Requirement 1.4**
        
        When due_date < invoice_date,
        Then validation should fail.
        """
        assume(due_date < invoice_date)
        
        with pytest.raises(ValidationError) as exc_info:
            InvoiceCreate(
                vendor_key="TEST",
                vendor_name="Test Vendor",
                invoice_number="INV-001",
                total_amount=Decimal('1000.00'),
                invoice_date=invoice_date,
                due_date=due_date
            )
        
        errors = exc_info.value.errors()
        assert any('due_date' in str(e) for e in errors)

    @settings(max_examples=50)
    @given(
        invoice_date=st.dates(
            min_value=date(2020, 1, 1),
            max_value=date(2030, 12, 31)
        )
    )
    def test_due_date_equal_to_invoice_date_accepted(self, invoice_date):
        """
        **Property**: Due dates equal to invoice dates should be accepted.
        **Validates: Requirement 1.4**
        
        When due_date == invoice_date,
        Then validation should succeed.
        """
        invoice = InvoiceCreate(
            vendor_key="TEST",
            vendor_name="Test Vendor",
            invoice_number="INV-001",
            total_amount=Decimal('1000.00'),
            invoice_date=invoice_date,
            due_date=invoice_date
        )
        
        assert invoice.due_date == invoice_date
        assert invoice.invoice_date == invoice_date

    @settings(max_examples=100)
    @given(
        vendor_key=st.text(min_size=1, max_size=100),
        invoice_number=alphanumeric_invoice_number(),
        vendor_name=valid_vendor_name(),
        total_amount=valid_amount(),
        dates=valid_date_pair()
    )
    def test_manual_entry_creates_pending_ocr_status(
        self,
        vendor_key,
        invoice_number,
        vendor_name,
        total_amount,
        dates
    ):
        """
        **Property**: Manual entry invoices should have OCR_Confidence = 1.0.
        **Validates: Requirement 1.4**
        
        When an invoice is created via manual entry with valid fields,
        Then the invoice should be created with status PENDING_OCR.
        """
        invoice_date, due_date = dates
        
        invoice = InvoiceCreate(
            vendor_key=vendor_key,
            vendor_name=vendor_name,
            invoice_number=invoice_number,
            total_amount=total_amount,
            invoice_date=invoice_date,
            due_date=due_date
        )
        
        # Manual entry invoices should have PENDING_OCR status by default
        assert invoice.status.value == "PENDING_OCR"

    @settings(max_examples=50)
    @given(
        vendor_name=st.text(min_size=0, max_size=0)
    )
    def test_empty_vendor_name_rejected(self, vendor_name):
        """
        **Property**: Empty vendor names should be rejected.
        **Validates: Requirement 1.4**
        
        When vendor_name is empty,
        Then validation should fail.
        """
        with pytest.raises(ValidationError) as exc_info:
            InvoiceCreate(
                vendor_key="TEST",
                vendor_name=vendor_name,
                invoice_number="INV-001",
                total_amount=Decimal('1000.00'),
                invoice_date=date(2024, 1, 1),
                due_date=date(2024, 2, 1)
            )
        
        errors = exc_info.value.errors()
        assert any('vendor_name' in str(e) for e in errors)

    @settings(max_examples=50)
    @given(
        invoice_number=st.text(min_size=0, max_size=0)
    )
    def test_empty_invoice_number_rejected(self, invoice_number):
        """
        **Property**: Empty invoice numbers should be rejected.
        **Validates: Requirement 1.4**
        
        When invoice_number is empty,
        Then validation should fail.
        """
        with pytest.raises(ValidationError) as exc_info:
            InvoiceCreate(
                vendor_key="TEST",
                vendor_name="Test Vendor",
                invoice_number=invoice_number,
                total_amount=Decimal('1000.00'),
                invoice_date=date(2024, 1, 1),
                due_date=date(2024, 2, 1)
            )
        
        errors = exc_info.value.errors()
        assert any('invoice_number' in str(e) for e in errors)
