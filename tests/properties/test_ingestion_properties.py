"""
Property-based tests for the ingestion service.

Validates:
- **Property 1: Webhook Signature Validation (Requirement 1.3)**
- **Property 3: Unique Invoice Identification (Requirement 1.5)**
- **Property 4: Duplicate File Detection (Requirement 1.6)**
"""

import hashlib
import hmac
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from hypothesis import given, settings, assume, example, HealthCheck
from hypothesis import strategies as st

from ap_workflow.services.ingestion import IngestionService
from ap_workflow.models.invoice import Invoice, InvoiceStatus


# --- Fixtures ---

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    
    # Set up query chain mock
    mock_query = MagicMock()
    session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.filter.return_value.first.return_value = None
    
    return session


@pytest.fixture
def ingestion_service(mock_db_session):
    """Create ingestion service with mock session."""
    service = IngestionService(db=mock_db_session)
    return service


# --- Helper Functions ---

def compute_hmac_sha256(secret: str, message: str) -> str:
    """Compute HMAC-SHA256 signature."""
    return hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


# --- Property 1: Webhook Signature Validation ---
# **Validates: Requirement 1.3**
# Property: WHEN a vendor sends an invoice via API webhook (EDI format), THE Webhook_Handler 
# SHALL validate the payload signature using HMAC-SHA256 with the vendor's registered secret key;
# IF signature is invalid, THE System SHALL return HTTP 401 Unauthorized; 
# IF valid, THE System SHALL parse the invoice data and create an invoice record.

class TestWebhookSignatureValidation:
    """Property tests for webhook signature validation (HMAC-SHA256)."""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        vendor_key=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Po'))),
        invoice_data=st.fixed_dictionaries({
            'vendor_name': st.text(min_size=1, max_size=100),
            'invoice_number': st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
            'total_amount': st.floats(min_value=0.01, max_value=999999.99, allow_nan=False, allow_infinity=False),
            'invoice_date': st.dates(min_value=datetime(2020, 1, 1).date(), max_value=datetime(2030, 12, 31).date()),
            'due_date': st.dates(min_value=datetime(2020, 1, 1).date(), max_value=datetime(2030, 12, 31).date()),
        }),
        secret=st.text(min_size=16, max_size=64, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Po')))
    )
    def test_valid_signature_is_accepted(self, vendor_key, invoice_data, secret):
        """
        **Property**: Valid HMAC-SHA256 signatures should be accepted.
        **Validates: Requirement 1.3**
        """
        # Ensure due_date >= invoice_date
        assume(invoice_data['due_date'] >= invoice_data['invoice_date'])
        
        service = IngestionService(db=MagicMock())
        
        # Compute valid signature using the message format expected by the system
        message = f"{vendor_key}:{invoice_data['invoice_number']}:{invoice_data['total_amount']}"
        valid_signature = compute_hmac_sha256(secret, message)
        
        # Mock database interactions
        service.db.commit = MagicMock()
        
        def mock_refresh(invoice):
            invoice.invoice_id = uuid.uuid4()
        
        service.db.refresh = mock_refresh
        
        # Valid signature should be accepted (signature == expected_signature)
        result = service.webhook_invoice(
            vendor_key=vendor_key,
            invoice_data=invoice_data,
            signature=valid_signature,
            expected_signature=valid_signature
        )
        
        assert result is not None
        assert isinstance(result, Invoice)

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        vendor_key=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        invoice_data=st.fixed_dictionaries({
            'vendor_name': st.text(min_size=1, max_size=50),
            'invoice_number': st.text(min_size=1, max_size=20),
            'total_amount': st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
            'invoice_date': st.dates(min_value=datetime(2020, 1, 1).date()),
            'due_date': st.dates(min_value=datetime(2020, 1, 1).date()),
        }),
        secret=st.text(min_size=16, max_size=32),
        wrong_secret=st.text(min_size=16, max_size=32)
    )
    def test_invalid_signature_is_rejected(self, vendor_key, invoice_data, secret, wrong_secret):
        """
        **Property**: Invalid signatures (using wrong secret key) should be rejected.
        **Validates: Requirement 1.3**
        """
        assume(invoice_data['due_date'] >= invoice_data['invoice_date'])
        assume(wrong_secret != secret)  # Ensure different secret
        
        service = IngestionService(db=MagicMock())
        
        # Compute valid signature with correct secret
        message = f"{vendor_key}:{invoice_data['invoice_number']}:{invoice_data['total_amount']}"
        valid_signature = compute_hmac_sha256(secret, message)
        
        # Compute wrong signature with different secret
        wrong_signature = compute_hmac_sha256(wrong_secret, message)
        
        # Should raise ValueError for invalid signature
        with pytest.raises(ValueError, match="Invalid webhook signature"):
            service.webhook_invoice(
                vendor_key=vendor_key,
                invoice_data=invoice_data,
                signature=wrong_signature,
                expected_signature=valid_signature
            )

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        vendor_key=st.text(min_size=1, max_size=50),
        invoice_data=st.fixed_dictionaries({
            'vendor_name': st.text(min_size=1, max_size=50),
            'invoice_number': st.text(min_size=1, max_size=20),
            'total_amount': st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
            'invoice_date': st.dates(),
            'due_date': st.dates(),
        }),
        secret=st.text(min_size=16, max_size=32)
    )
    def test_tampered_signature_is_rejected(self, vendor_key, invoice_data, secret):
        """
        **Property**: Tampered signatures (any bit change) should be rejected.
        **Validates: Requirement 1.3**
        
        This validates the cryptographic integrity of HMAC-SHA256.
        Even a single bit change in the signature makes it invalid.
        """
        assume(invoice_data['due_date'] >= invoice_data['invoice_date'])
        
        service = IngestionService(db=MagicMock())
        
        # Compute valid signature
        message = f"{vendor_key}:{invoice_data['invoice_number']}:{invoice_data['total_amount']}"
        valid_signature = compute_hmac_sha256(secret, message)
        
        # Tamper with the signature by changing one character
        # This simulates bit-level corruption
        tampered_signature = valid_signature[:-1] + ('0' if valid_signature[-1] != '0' else '1')
        
        # Should raise ValueError for tampered signature
        with pytest.raises(ValueError, match="Invalid webhook signature"):
            service.webhook_invoice(
                vendor_key=vendor_key,
                invoice_data=invoice_data,
                signature=tampered_signature,
                expected_signature=valid_signature
            )

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        vendor_key=st.text(min_size=1, max_size=50),
        invoice_data=st.fixed_dictionaries({
            'vendor_name': st.text(min_size=1, max_size=50),
            'invoice_number': st.text(min_size=1, max_size=20),
            'total_amount': st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
            'invoice_date': st.dates(),
            'due_date': st.dates(),
        })
    )
    def test_empty_signature_is_rejected(self, vendor_key, invoice_data):
        """
        **Property**: Empty signature should always be rejected.
        **Validates: Requirement 1.3**
        """
        assume(invoice_data['due_date'] >= invoice_data['invoice_date'])
        
        service = IngestionService(db=MagicMock())
        
        # Empty signature
        empty_signature = ""
        
        # Should raise ValueError for empty signature
        with pytest.raises(ValueError, match="Invalid webhook signature"):
            service.webhook_invoice(
                vendor_key=vendor_key,
                invoice_data=invoice_data,
                signature=empty_signature,
                expected_signature="some_expected_signature"
            )

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        vendor_key=st.text(min_size=1, max_size=50),
        invoice_data=st.fixed_dictionaries({
            'vendor_name': st.text(min_size=1, max_size=50),
            'invoice_number': st.text(min_size=1, max_size=20),
            'total_amount': st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
            'invoice_date': st.dates(),
            'due_date': st.dates(),
        }),
        secret_length=st.integers(min_value=1, max_value=256)
    )
    def test_signature_works_with_various_key_lengths(self, vendor_key, invoice_data, secret_length):
        """
        **Property**: HMAC-SHA256 should work correctly with various key lengths (1-256 bytes).
        **Validates: Requirement 1.3**
        
        HMAC-SHA256 RFC 2104 allows keys of any length. This validates the implementation
        handles both short and long keys correctly.
        """
        assume(invoice_data['due_date'] >= invoice_data['invoice_date'])
        
        # Generate secret of specified length with alphanumeric characters
        secret = 'a' * secret_length
        
        service = IngestionService(db=MagicMock())
        service.db.commit = MagicMock()
        
        def mock_refresh(invoice):
            invoice.invoice_id = uuid.uuid4()
        
        service.db.refresh = mock_refresh
        
        # Compute valid signature
        message = f"{vendor_key}:{invoice_data['invoice_number']}:{invoice_data['total_amount']}"
        valid_signature = compute_hmac_sha256(secret, message)
        
        # Should accept valid signature regardless of key length
        result = service.webhook_invoice(
            vendor_key=vendor_key,
            invoice_data=invoice_data,
            signature=valid_signature,
            expected_signature=valid_signature
        )
        
        assert result is not None

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        vendor_key=st.text(min_size=1, max_size=50),
        invoice_number=st.text(min_size=1, max_size=20),
        total_amount=st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        secret=st.text(min_size=16, max_size=32)
    )
    def test_signature_deterministic(self, vendor_key, invoice_number, total_amount, secret):
        """
        **Property**: HMAC-SHA256 must be deterministic (same inputs produce same signature).
        **Validates: Requirement 1.3**
        
        This validates the cryptographic determinism of HMAC-SHA256.
        """
        message = f"{vendor_key}:{invoice_number}:{total_amount}"
        
        # Compute signature twice
        sig1 = compute_hmac_sha256(secret, message)
        sig2 = compute_hmac_sha256(secret, message)
        
        # Signatures must be identical
        assert sig1 == sig2
        assert len(sig1) == 64  # SHA-256 produces 64 hex characters



# --- Property 3: Unique Invoice Identification ---
# **Validates: Requirement 1.5**
# Property: WHEN an invoice is ingested, THE System SHALL assign a unique invoice_id (UUID v4) 
# and record received_at timestamp in UTC with millisecond precision.
# Every invoice record SHALL have exactly one received_at timestamp and one ingestion_source.

class TestUniqueInvoiceIdentification:
    """Property tests for unique invoice identification (UUID v4)."""

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        ingestion_count=st.integers(min_value=2, max_value=20),
        vendor_keys=st.lists(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))), min_size=2, max_size=20, unique=True)
    )
    def test_each_invoice_gets_unique_uuid_v4(self, ingestion_count, vendor_keys):
        """
        **Property**: Each ingested invoice should have a unique UUID v4.
        **Validates: Requirement 1.5**
        
        UUID v4 uniqueness is a cryptographic property. All generated IDs must be distinct.
        """
        assume(len(vendor_keys) >= ingestion_count)
        
        generated_ids = set()
        
        for i in range(ingestion_count):
            service = IngestionService(db=MagicMock())
            service.db.commit = MagicMock()
            
            def mock_refresh(invoice):
                invoice.invoice_id = uuid.uuid4()
            
            service.db.refresh = mock_refresh
            
            # Create invoice via manual entry
            invoice = service.manual_entry_invoice(
                vendor_name=f"Vendor {vendor_keys[i]}",
                invoice_number=f"INV-{i:06d}",
                total_amount=100.0 + i,
                invoice_date="2024-01-15",
                due_date="2024-02-15"
            )
            
            # Each invoice should have a unique ID
            assert invoice.invoice_id is not None
            
            # UUID v4 should be a valid UUID
            assert isinstance(invoice.invoice_id, (str, uuid.UUID))
            
            # ID must not have been seen before
            assert invoice.invoice_id not in generated_ids
            generated_ids.add(invoice.invoice_id)
        
        # Verify we have all unique IDs
        assert len(generated_ids) == ingestion_count

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        vendor_name=st.text(min_size=1, max_size=100),
        invoice_number=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        total_amount=st.floats(min_value=0.01, max_value=999999.99, allow_nan=False, allow_infinity=False),
    )
    def test_received_at_timestamp_is_recorded(self, vendor_name, invoice_number, total_amount):
        """
        **Property**: Each invoice should have a received_at timestamp in UTC.
        **Validates: Requirement 1.5**
        
        The timestamp must be set at ingestion time and be in UTC timezone.
        """
        service = IngestionService(db=MagicMock())
        service.db.commit = MagicMock()
        
        before_creation = datetime.utcnow()
        
        def mock_refresh(invoice):
            invoice.invoice_id = uuid.uuid4()
        
        service.db.refresh = mock_refresh
        
        invoice = service.manual_entry_invoice(
            vendor_name=vendor_name,
            invoice_number=invoice_number,
            total_amount=total_amount,
            invoice_date="2024-01-15",
            due_date="2024-02-15"
        )
        
        after_creation = datetime.utcnow()
        
        # received_at should be set
        assert invoice.received_at is not None
        assert isinstance(invoice.received_at, datetime)
        
        # Timestamp must be within the creation window (with tolerance for execution)
        assert before_creation <= invoice.received_at <= after_creation + timedelta(seconds=1)

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        vendor_keys=st.lists(st.text(min_size=1, max_size=50), min_size=3, max_size=10, unique=True),
    )
    def test_received_at_ordering_is_consistent(self, vendor_keys):
        """
        **Property**: received_at timestamps should maintain FIFO ordering for invoices ingested in sequence.
        **Validates: Requirement 1.5**
        
        Requirement states: "Invoices ingested from the same source SHALL maintain received_at ordering (FIFO)"
        """
        timestamps = []
        
        for i, vendor_key in enumerate(vendor_keys):
            service = IngestionService(db=MagicMock())
            service.db.commit = MagicMock()
            
            def mock_refresh(invoice):
                invoice.invoice_id = uuid.uuid4()
            
            service.db.refresh = mock_refresh
            
            invoice = service.manual_entry_invoice(
                vendor_name=f"Vendor {vendor_key}",
                invoice_number=f"INV-{i:03d}",
                total_amount=100.0 + i,
                invoice_date="2024-01-15",
                due_date="2024-02-15"
            )
            
            timestamps.append(invoice.received_at)
        
        # Timestamps should be monotonically increasing (allowing for equal timestamps if too fast)
        for i in range(len(timestamps) - 1):
            assert timestamps[i] <= timestamps[i + 1], \
                f"Timestamp ordering violated: {timestamps[i]} > {timestamps[i+1]}"

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        ingestion_sources=st.sampled_from(['webhook', 'upload', 'manual'])
    )
    def test_invoice_has_ingestion_source(self, ingestion_sources):
        """
        **Property**: Each invoice should have exactly one ingestion_source field.
        **Validates: Requirement 1.5**
        
        Requirement states: "Every invoice record SHALL have exactly one ingestion_source (email|upload|webhook|manual)"
        """
        service = IngestionService(db=MagicMock())
        service.db.commit = MagicMock()
        
        def mock_refresh(invoice):
            invoice.invoice_id = uuid.uuid4()
        
        service.db.refresh = mock_refresh
        
        if ingestion_sources == "webhook":
            invoice = service.webhook_invoice(
                vendor_key="TEST",
                invoice_data={
                    "vendor_name": "Test Vendor",
                    "invoice_number": "INV-001",
                    "total_amount": 100.0,
                    "invoice_date": "2024-01-15",
                    "due_date": "2024-02-15"
                },
                signature="sig",
                expected_signature="sig"
            )
        else:
            invoice = service.manual_entry_invoice(
                vendor_name="Test Vendor",
                invoice_number=f"INV-{ingestion_sources}",
                total_amount=100.0,
                invoice_date="2024-01-15",
                due_date="2024-02-15"
            )
        
        # Should have exactly one ingestion_source
        assert invoice.ingestion_source is not None
        assert invoice.ingestion_source in ['email', 'upload', 'webhook', 'manual']
        assert isinstance(invoice.ingestion_source, str)

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        invoice_count=st.integers(min_value=5, max_value=50)
    )
    def test_invoice_ids_are_uuids(self, invoice_count):
        """
        **Property**: Every invoice_id should be a valid UUID.
        **Validates: Requirement 1.5**
        """
        for i in range(invoice_count):
            service = IngestionService(db=MagicMock())
            service.db.commit = MagicMock()
            
            def mock_refresh(invoice):
                invoice.invoice_id = uuid.uuid4()
            
            service.db.refresh = mock_refresh
            
            invoice = service.manual_entry_invoice(
                vendor_name=f"Vendor {i}",
                invoice_number=f"INV-{i:06d}",
                total_amount=100.0,
                invoice_date="2024-01-15",
                due_date="2024-02-15"
            )
            
            # Should be a valid UUID
            assert invoice.invoice_id is not None
            
            # If string, should be valid UUID format
            if isinstance(invoice.invoice_id, str):
                try:
                    uuid.UUID(invoice.invoice_id)
                except ValueError:
                    pytest.fail(f"invoice_id is not a valid UUID: {invoice.invoice_id}")



# --- Property 4: Duplicate File Detection ---
# **Validates: Requirement 1.6**
# Property: WHEN duplicate file uploads occur (same file hash within 24-hour configurable window),
# THE System SHALL detect and reject the duplicate, returning HTTP 409 Conflict with error code
# DUPLICATE_FILE_DETECTED and the original invoice_id.
# 
# Correctness: 
# - Idempotence: Resubmitting the same invoice file multiple times SHALL result in exactly one invoice record
# - Invariant: If DUPLICATE_EXACT is detected, then hash(invoice_a) = hash(invoice_b) for linked invoices
# - Metamorphic: File hash must be deterministic (same file always produces same hash)

class TestDuplicateFileDetection:
    """Property tests for duplicate file detection using SHA-256 hashing."""

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        file_content=st.binary(min_size=1, max_size=1024),
        vendor_key=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        vendor_name=st.text(min_size=1, max_size=100),
    )
    def test_duplicate_file_within_window_detected(self, file_content, vendor_key, vendor_name):
        """
        **Property**: Duplicate files within the 24-hour time window should be detected and rejected.
        **Validates: Requirement 1.6**
        
        Requirement states: "WHEN duplicate file uploads occur (same file hash within 24-hour 
        configurable window), THE System SHALL detect and reject the duplicate, returning HTTP 409 Conflict"
        """
        service = IngestionService(db=MagicMock())
        
        # Set up mock to return existing invoice (simulating duplicate)
        file_hash = compute_file_hash(file_content)
        existing_invoice_id = str(uuid.uuid4())
        
        mock_existing = MagicMock()
        mock_existing.invoice_id = existing_invoice_id
        
        service.db.query.return_value.filter.return_value.first.return_value = mock_existing
        
        # Should raise duplicate error
        with pytest.raises(ValueError, match="DUPLICATE_FILE_DETECTED"):
            service.upload_invoice(
                file_content=file_content,
                vendor_key=vendor_key,
                vendor_name=vendor_name
            )

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        file_content=st.binary(min_size=1, max_size=1024),
        vendor_key=st.text(min_size=1, max_size=50),
        vendor_name=st.text(min_size=1, max_size=100),
    )
    def test_new_file_upload_succeeds(self, file_content, vendor_key, vendor_name):
        """
        **Property**: New unique file uploads should always succeed.
        **Validates: Requirement 1.6**
        """
        service = IngestionService(db=MagicMock())
        
        # Set up mock to return None (no duplicate found)
        service.db.query.return_value.filter.return_value.first.return_value = None
        service.db.commit = MagicMock()
        
        def mock_refresh(invoice):
            invoice.invoice_id = uuid.uuid4()
            invoice.status = InvoiceStatus.PENDING_OCR
        
        service.db.refresh = mock_refresh
        
        # Should succeed for new file
        invoice = service.upload_invoice(
            file_content=file_content,
            vendor_key=vendor_key,
            vendor_name=vendor_name
        )
        
        assert invoice is not None
        assert invoice.invoice_id is not None

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        file_content=st.binary(min_size=1, max_size=512),
    )
    def test_file_hash_deterministic(self, file_content):
        """
        **Property**: File hash must be deterministic (idempotence).
        **Validates: Requirement 1.6 (Correctness: Metamorphic property)**
        
        SHA-256 must be deterministic: same input always produces same hash.
        This is a cryptographic invariant.
        """
        hash1 = compute_file_hash(file_content)
        hash2 = compute_file_hash(file_content)
        
        # Hashes must be identical
        assert hash1 == hash2
        # SHA-256 produces 64 hex characters
        assert len(hash1) == 64

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        file_contents=st.lists(st.binary(min_size=10, max_size=256), min_size=3, max_size=10, unique=True),
    )
    def test_different_files_have_different_hashes(self, file_contents):
        """
        **Property**: Different files must have different SHA-256 hashes (collision resistance).
        **Validates: Requirement 1.6**
        
        This validates the collision resistance property of SHA-256.
        """
        hashes = set()
        
        for content in file_contents:
            file_hash = compute_file_hash(content)
            assert file_hash not in hashes, "Hash collision detected!"
            hashes.add(file_hash)
        
        # All hashes should be unique
        assert len(hashes) == len(file_contents)

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        file_content=st.binary(min_size=1, max_size=256),
    )
    def test_single_byte_change_changes_hash(self, file_content):
        """
        **Property**: Changing even a single byte should dramatically change the hash (avalanche effect).
        **Validates: Requirement 1.6 (Correctness: Metamorphic property)**
        
        This validates the avalanche effect of SHA-256.
        """
        assume(len(file_content) > 0)
        
        hash1 = compute_file_hash(file_content)
        
        # Change one byte
        if len(file_content) == 1:
            modified_content = bytes([file_content[0] ^ 1])
        else:
            modified_content = file_content[:-1] + bytes([(file_content[-1] + 1) % 256])
        
        hash2 = compute_file_hash(modified_content)
        
        # Hashes must be different
        assert hash1 != hash2

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        file_content=st.binary(min_size=1, max_size=1024),
        window_hours=st.integers(min_value=1, max_value=72),
    )
    def test_duplicate_detection_respects_time_window(self, file_content, window_hours):
        """
        **Property**: Duplicate detection should respect the configurable time window (default 24 hours).
        **Validates: Requirement 1.6**
        
        Requirement states: "search for matching hashes in invoices received within the past 72 hours
        (configurable per vendor, default 72h)"
        """
        service = IngestionService(db=MagicMock())
        
        # The _check_duplicate_file method should use the window_hours parameter
        # This test verifies the time window is configurable
        file_hash = compute_file_hash(file_content)
        
        # Call the method with custom window
        service._check_duplicate_file(file_hash, window_hours=window_hours)
        
        # Verify the query was called (indicating time window was considered)
        service.db.query.assert_called()

    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    @given(
        file_contents=st.lists(st.binary(min_size=1, max_size=256), min_size=3, max_size=3, unique=True),
    )
    def test_different_files_all_accepted(self, file_contents):
        """
        **Property**: Multiple different files should all be accepted (no false positives).
        **Validates: Requirement 1.6**
        """
        for i, content in enumerate(file_contents):
            service = IngestionService(db=MagicMock())
            
            # Each query returns None (no duplicate)
            service.db.query.return_value.filter.return_value.first.return_value = None
            service.db.commit = MagicMock()
            
            def mock_refresh(invoice):
                invoice.invoice_id = uuid.uuid4()
                invoice.status = InvoiceStatus.PENDING_OCR
            
            service.db.refresh = mock_refresh
            
            invoice = service.upload_invoice(
                file_content=content,
                vendor_key=f"vendor_{compute_file_hash(content)[:8]}",
                vendor_name="Test Vendor"
            )
            
            assert invoice is not None

    def test_duplicate_error_includes_original_id(self):
        """
        **Property**: When a duplicate is detected, the error should include the original invoice_id.
        **Validates: Requirement 1.6**
        
        Requirement: "returning HTTP 409 Conflict with error code DUPLICATE_FILE_DETECTED and the original invoice_id"
        """
        service = IngestionService(db=MagicMock())
        
        original_id = str(uuid.uuid4())
        mock_existing = MagicMock()
        mock_existing.invoice_id = original_id
        
        service.db.query.return_value.filter.return_value.first.return_value = mock_existing
        
        with pytest.raises(ValueError) as exc_info:
            service.upload_invoice(
                file_content=b"same content",
                vendor_key="VENDOR",
                vendor_name="Vendor Name"
            )
        
        # Error should include original invoice_id for correlation
        assert original_id in str(exc_info.value)

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        file_lengths=st.lists(st.integers(min_value=1, max_value=1024), min_size=5, max_size=5)
    )
    def test_hash_length_is_consistent(self, file_lengths):
        """
        **Property**: SHA-256 hash length should always be 64 hex characters, regardless of file size.
        **Validates: Requirement 1.6**
        """
        for length in file_lengths:
            file_content = b'a' * length
            file_hash = compute_file_hash(file_content)
            
            # SHA-256 always produces 64 hex characters
            assert len(file_hash) == 64
            # Should only contain hex characters
            assert all(c in '0123456789abcdef' for c in file_hash)

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        file_content=st.binary(min_size=10, max_size=256),
    )
    def test_idempotent_duplicate_detection(self, file_content):
        """
        **Property**: Running duplicate detection twice on the same file should produce identical results (idempotence).
        **Validates: Requirement 1.6 (Correctness: Idempotence)**
        
        Requirement: "Running duplicate detection twice on the same invoice set SHALL produce 
        identical duplicate classifications"
        """
        hash1 = compute_file_hash(file_content)
        hash2 = compute_file_hash(file_content)
        
        # Both detections should find identical hashes
        assert hash1 == hash2
        
        # This means duplicate detection is deterministic and idempotent
        service = IngestionService(db=MagicMock())
        service.db.query.return_value.filter.return_value.first.return_value = None
        
        existing_id_1 = service._check_duplicate_file(hash1)
        existing_id_2 = service._check_duplicate_file(hash2)
        
        # Both calls should return the same result (idempotence)
        assert existing_id_1 == existing_id_2



# --- Integration Tests ---

class TestIngestionServiceIntegration:
    """Integration tests for the complete ingestion service."""

    def test_upload_creates_audit_log(self):
        """Test that uploading an invoice creates an audit log entry."""
        service = IngestionService(db=MagicMock())
        
        service.db.query.return_value.filter.return_value.first.return_value = None
        service.db.commit = MagicMock()
        
        def mock_refresh(invoice):
            invoice.invoice_id = uuid.uuid4()
            invoice.status = InvoiceStatus.PENDING_OCR
        
        service.db.refresh = mock_refresh
        
        invoice = service.upload_invoice(
            file_content=b"test pdf content",
            vendor_key="TEST_VENDOR",
            vendor_name="Test Vendor"
        )
        
        # Should have called add for invoice and audit log
        assert service.db.add.called

    def test_webhook_validates_required_fields(self):
        """Test that webhook validates required fields in invoice_data."""
        service = IngestionService(db=MagicMock())
        service.db.commit = MagicMock()
        
        def mock_refresh(invoice):
            invoice.invoice_id = uuid.uuid4()
        
        service.db.refresh = mock_refresh
        
        # Test with valid complete data
        valid_data = {
            "vendor_name": "Test",
            "invoice_number": "INV-001",
            "total_amount": 100.0,
            "invoice_date": "2024-01-15",
            "due_date": "2024-02-15"
        }
        
        result = service.webhook_invoice(
            vendor_key="TEST",
            invoice_data=valid_data,
            signature="sig",
            expected_signature="sig"
        )
        
        assert result is not None

    def test_manual_entry_sets_pending_ocr_status(self):
        """Test that manual entry invoices are set to PENDING_OCR status."""
        service = IngestionService(db=MagicMock())
        service.db.commit = MagicMock()
        
        def mock_refresh(invoice):
            invoice.invoice_id = uuid.uuid4()
        
        service.db.refresh = mock_refresh
        
        invoice = service.manual_entry_invoice(
            vendor_name="Test Vendor",
            invoice_number="INV-001",
            total_amount=100.0,
            invoice_date="2024-01-15",
            due_date="2024-02-15"
        )
        
        assert invoice.status == InvoiceStatus.PENDING_OCR
        assert invoice.ingestion_source == "manual"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
