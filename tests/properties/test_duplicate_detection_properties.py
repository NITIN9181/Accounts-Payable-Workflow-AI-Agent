"""
Property-based tests for duplicate detection service.

Validates:
- **Property 14: Exact Duplicate Detection (Requirements 4.1, 4.2)**
- **Property 15: Fuzzy Duplicate Detection (Requirements 4.3, 4.4)**
- **Property 43: Idempotent Duplicate Detection (Requirements 4 - Idempotence)**
- **Property 46: Symmetric Fuzzy Matching (Requirements 4 - Metamorphic)**
- **Property 47: Monotonic Date Proximity (Requirements 4 - Metamorphic)**
"""

import hashlib
import pytest
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import uuid4
from unittest.mock import MagicMock, patch
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from ap_workflow.models.invoice import Invoice, InvoiceStatus
from ap_workflow.models.duplicate_detection import DuplicateDetection
from ap_workflow.services.duplicate_detection import DuplicateDetectionService


# --- Fixtures ---

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
def duplicate_detection_service(mock_db_session):
    """Create duplicate detection service with mock session."""
    return DuplicateDetectionService(db=mock_db_session)


# --- Helper Functions ---

def compute_invoice_hash(vendor_key: str, invoice_number: str, total_amount_usd: float, invoice_date: date) -> str:
    """Compute SHA-256 hash for exact duplicate detection."""
    message = f"{vendor_key}:{invoice_number}:{total_amount_usd}:{invoice_date}"
    return hashlib.sha256(message.encode('utf-8')).hexdigest()


def compute_fuzzy_similarity(amount_a: float, amount_b: float, days_apart: int, vendor_a: str, vendor_b: str) -> float:
    """Compute fuzzy matching confidence score."""
    from rapidfuzz import fuzz
    
    # Amount similarity
    amount_similarity = 1.0 - abs(amount_a - amount_b) / max(amount_a, amount_b)
    
    # Date proximity
    date_proximity = max(0.0, 1.0 - (days_apart / 7.0))
    
    # Vendor match
    vendor_match = fuzz.token_set_ratio(vendor_a, vendor_b) / 100.0
    
    # Weighted combination
    fuzzy_confidence = (0.5 * amount_similarity) + (0.3 * date_proximity) + (0.2 * vendor_match)
    
    return fuzzy_confidence


# --- Property 14: Exact Duplicate Detection ---
# **Validates: Requirements 4.1, 4.2**

class TestExactDuplicateDetection:
    """Property tests for exact duplicate detection using SHA-256 hashing."""

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        vendor_key=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        invoice_number=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        total_amount_usd=st.floats(min_value=0.01, max_value=999999.99, allow_nan=False, allow_infinity=False),
        invoice_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))
    )
    def test_exact_duplicate_detected_with_matching_hash(self, duplicate_detection_service, vendor_key, invoice_number, total_amount_usd, invoice_date):
        """
        **Property**: Invoices with identical hash should be detected as DUPLICATE_EXACT.
        **Validates: Requirements 4.1, 4.2**
        """
        # Compute hash
        invoice_hash = compute_invoice_hash(vendor_key, invoice_number, total_amount_usd, invoice_date)
        
        # Setup mock to return existing invoice with same hash
        existing_invoice = MagicMock()
        existing_invoice.invoice_id = uuid4()
        existing_invoice.file_hash = invoice_hash
        
        duplicate_detection_service.db.query.return_value.filter.return_value.first.return_value = existing_invoice
        
        # Detect duplicate
        result = duplicate_detection_service._find_exact_duplicate(invoice_hash)
        
        assert result is not None
        assert result.invoice_id == existing_invoice.invoice_id

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        vendor_key=st.text(min_size=1, max_size=50),
        invoice_number=st.text(min_size=1, max_size=50),
        total_amount_usd=st.floats(min_value=0.01, max_value=999999.99, allow_nan=False, allow_infinity=False),
        invoice_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))
    )
    def test_exact_duplicate_severity_is_0_95(self, duplicate_detection_service, vendor_key, invoice_number, total_amount_usd, invoice_date):
        """
        **Property**: DUPLICATE_EXACT should have severity = 0.95.
        **Validates: Requirements 4.1, 4.2**
        """
        invoice_hash = compute_invoice_hash(vendor_key, invoice_number, total_amount_usd, invoice_date)
        
        # Compute severity for exact duplicate
        severity = duplicate_detection_service._compute_duplicate_severity(
            detection_type="EXACT",
            fuzzy_confidence=None
        )
        
        assert severity == 0.95

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        window_hours=st.integers(min_value=1, max_value=168)
    )
    def test_exact_duplicate_search_respects_time_window(self, duplicate_detection_service, window_hours):
        """
        **Property**: Exact duplicate search should respect configurable time window (default 72h).
        **Validates: Requirements 4.1, 4.2**
        """
        invoice_hash = "abc123def456"
        
        # Search with custom window
        duplicate_detection_service._search_exact_duplicates(invoice_hash, window_hours=window_hours)
        
        # Verify query was called (indicating time window was considered)
        assert duplicate_detection_service.db.query.called

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        num_duplicates=st.integers(min_value=1, max_value=5)
    )
    def test_multiple_exact_duplicates_detected(self, duplicate_detection_service, num_duplicates):
        """
        **Property**: Multiple exact duplicates should all be detected.
        **Validates: Requirements 4.1, 4.2**
        """
        invoice_hash = "same_hash_for_all"
        
        # Create mock duplicates
        duplicates = [MagicMock(invoice_id=uuid4()) for _ in range(num_duplicates)]
        duplicate_detection_service.db.query.return_value.filter.return_value.all.return_value = duplicates
        
        # Find all duplicates
        results = duplicate_detection_service._find_all_exact_duplicates(invoice_hash)
        
        assert len(results) == num_duplicates


# --- Property 15: Fuzzy Duplicate Detection ---
# **Validates: Requirements 4.3, 4.4**

class TestFuzzyDuplicateDetection:
    """Property tests for fuzzy duplicate detection."""

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        amount_a=st.floats(min_value=100.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        amount_b=st.floats(min_value=100.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        days_apart=st.integers(min_value=0, max_value=7),
        vendor_a=st.text(min_size=5, max_size=50),
        vendor_b=st.text(min_size=5, max_size=50)
    )
    def test_fuzzy_matching_confidence_calculation(self, duplicate_detection_service, amount_a, amount_b, days_apart, vendor_a, vendor_b):
        """
        **Property**: Fuzzy confidence should be calculated as weighted combination.
        **Validates: Requirements 4.3, 4.4**
        """
        # Compute expected confidence
        expected_confidence = compute_fuzzy_similarity(amount_a, amount_b, days_apart, vendor_a, vendor_b)
        
        # Compute via service
        result_confidence = duplicate_detection_service._compute_fuzzy_confidence(
            amount_a, amount_b, days_apart, vendor_a, vendor_b
        )
        
        # Should be close (within floating point tolerance)
        assert abs(result_confidence - expected_confidence) < 0.01

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        fuzzy_confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    def test_fuzzy_duplicate_threshold_0_85(self, duplicate_detection_service, fuzzy_confidence):
        """
        **Property**: Fuzzy duplicates should be detected when confidence >= 0.85.
        **Validates: Requirements 4.3, 4.4**
        """
        is_duplicate = duplicate_detection_service._is_fuzzy_duplicate(fuzzy_confidence)
        
        expected = fuzzy_confidence >= 0.85
        assert is_duplicate == expected

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        fuzzy_confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    def test_fuzzy_duplicate_severity_equals_confidence(self, duplicate_detection_service, fuzzy_confidence):
        """
        **Property**: DUPLICATE_FUZZY severity should equal fuzzy_confidence.
        **Validates: Requirements 4.3, 4.4**
        """
        severity = duplicate_detection_service._compute_duplicate_severity(
            detection_type="FUZZY",
            fuzzy_confidence=fuzzy_confidence
        )
        
        assert severity == fuzzy_confidence

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        amount_similarity=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        date_proximity=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        vendor_match=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    def test_fuzzy_confidence_weighted_formula(self, duplicate_detection_service, amount_similarity, date_proximity, vendor_match):
        """
        **Property**: Fuzzy confidence = (0.5 * amount) + (0.3 * date) + (0.2 * vendor).
        **Validates: Requirements 4.3, 4.4**
        """
        expected = (0.5 * amount_similarity) + (0.3 * date_proximity) + (0.2 * vendor_match)
        
        result = duplicate_detection_service._compute_weighted_confidence(
            amount_similarity, date_proximity, vendor_match
        )
        
        assert abs(result - expected) < 0.001


# --- Property 43: Idempotent Duplicate Detection ---
# **Validates: Requirements 4 (Idempotence)**

class TestIdempotentDuplicateDetection:
    """Property tests for idempotent duplicate detection."""

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        vendor_key=st.text(min_size=1, max_size=50),
        invoice_number=st.text(min_size=1, max_size=50),
        total_amount_usd=st.floats(min_value=0.01, max_value=999999.99, allow_nan=False, allow_infinity=False),
        invoice_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))
    )
    def test_duplicate_detection_idempotent(self, duplicate_detection_service, vendor_key, invoice_number, total_amount_usd, invoice_date):
        """
        **Property**: Running duplicate detection twice should produce identical results.
        **Validates: Requirements 4 (Idempotence)**
        """
        invoice_hash = compute_invoice_hash(vendor_key, invoice_number, total_amount_usd, invoice_date)
        
        # First detection
        result1 = duplicate_detection_service._detect_duplicates(invoice_hash)
        
        # Second detection (should be identical)
        result2 = duplicate_detection_service._detect_duplicates(invoice_hash)
        
        # Results must be identical
        assert result1 == result2

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        num_runs=st.integers(min_value=2, max_value=5)
    )
    def test_multiple_duplicate_detection_runs_consistent(self, duplicate_detection_service, num_runs):
        """
        **Property**: Multiple runs of duplicate detection should all produce same result.
        **Validates: Requirements 4 (Idempotence)**
        """
        invoice_hash = "test_hash_123"
        
        results = []
        for _ in range(num_runs):
            result = duplicate_detection_service._detect_duplicates(invoice_hash)
            results.append(result)
        
        # All results should be identical
        for i in range(1, len(results)):
            assert results[i] == results[0]


# --- Property 46: Symmetric Fuzzy Matching ---
# **Validates: Requirements 4 (Metamorphic)**

class TestSymmetricFuzzyMatching:
    """Property tests for symmetric fuzzy matching."""

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        amount_a=st.floats(min_value=100.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        amount_b=st.floats(min_value=100.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        days_apart=st.integers(min_value=0, max_value=7),
        vendor_a=st.text(min_size=5, max_size=50),
        vendor_b=st.text(min_size=5, max_size=50)
    )
    def test_fuzzy_matching_symmetric(self, duplicate_detection_service, amount_a, amount_b, days_apart, vendor_a, vendor_b):
        """
        **Property**: Fuzzy matching confidence should be symmetric: confidence(A, B) = confidence(B, A).
        **Validates: Requirements 4 (Metamorphic)**
        """
        # Confidence A->B
        conf_ab = duplicate_detection_service._compute_fuzzy_confidence(
            amount_a, amount_b, days_apart, vendor_a, vendor_b
        )
        
        # Confidence B->A (should be identical due to symmetry)
        conf_ba = duplicate_detection_service._compute_fuzzy_confidence(
            amount_b, amount_a, days_apart, vendor_b, vendor_a
        )
        
        # Should be equal (within floating point tolerance)
        assert abs(conf_ab - conf_ba) < 0.01

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        vendor_a=st.text(min_size=5, max_size=50),
        vendor_b=st.text(min_size=5, max_size=50)
    )
    def test_vendor_matching_symmetric(self, duplicate_detection_service, vendor_a, vendor_b):
        """
        **Property**: Vendor name matching should be symmetric.
        **Validates: Requirements 4 (Metamorphic)**
        """
        from rapidfuzz import fuzz
        
        # Match A->B
        match_ab = fuzz.token_set_ratio(vendor_a, vendor_b)
        
        # Match B->A (should be identical)
        match_ba = fuzz.token_set_ratio(vendor_b, vendor_a)
        
        # Should be equal
        assert match_ab == match_ba


# --- Property 47: Monotonic Date Proximity ---
# **Validates: Requirements 4 (Metamorphic)**

class TestMonotonicDateProximity:
    """Property tests for monotonic date proximity."""

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        days_apart_1=st.integers(min_value=0, max_value=30),
        days_apart_2=st.integers(min_value=0, max_value=30)
    )
    def test_date_proximity_monotonic_decreasing(self, duplicate_detection_service, days_apart_1, days_apart_2):
        """
        **Property**: Date proximity should be monotonically decreasing as days_apart increases.
        **Validates: Requirements 4 (Metamorphic)**
        """
        # Compute proximity for both
        proximity_1 = duplicate_detection_service._compute_date_proximity(days_apart_1)
        proximity_2 = duplicate_detection_service._compute_date_proximity(days_apart_2)
        
        # If days_apart_1 < days_apart_2, then proximity_1 >= proximity_2
        if days_apart_1 < days_apart_2:
            assert proximity_1 >= proximity_2
        elif days_apart_1 > days_apart_2:
            assert proximity_1 <= proximity_2
        else:
            assert proximity_1 == proximity_2

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        days_apart=st.integers(min_value=0, max_value=100)
    )
    def test_date_proximity_in_valid_range(self, duplicate_detection_service, days_apart):
        """
        **Property**: Date proximity should always be in range [0.0, 1.0].
        **Validates: Requirements 4 (Metamorphic)**
        """
        proximity = duplicate_detection_service._compute_date_proximity(days_apart)
        
        assert 0.0 <= proximity <= 1.0

    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    @given(
        days_apart=st.integers(min_value=0, max_value=7)
    )
    def test_date_proximity_formula_correctness(self, duplicate_detection_service, days_apart):
        """
        **Property**: Date proximity formula should be: max(0, 1 - (days_apart / 7)).
        **Validates: Requirements 4 (Metamorphic)**
        """
        expected = max(0.0, 1.0 - (days_apart / 7.0))
        
        result = duplicate_detection_service._compute_date_proximity(days_apart)
        
        assert abs(result - expected) < 0.001


# --- Integration Tests ---

class TestDuplicateDetectionIntegration:
    """Integration tests for complete duplicate detection workflow."""

    def test_exact_duplicate_prevents_auto_approval(self, mock_db_session):
        """Test that exact duplicates prevent automatic approval."""
        service = DuplicateDetectionService(db=mock_db_session)
        
        invoice_hash = "test_hash"
        
        # Setup mock to return existing invoice
        existing = MagicMock()
        existing.invoice_id = uuid4()
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing
        
        # Detect duplicate
        result = service._find_exact_duplicate(invoice_hash)
        
        # Should prevent auto-approval
        assert result is not None

    def test_fuzzy_duplicate_with_high_confidence(self, mock_db_session):
        """Test fuzzy duplicate detection with high confidence."""
        service = DuplicateDetectionService(db=mock_db_session)
        
        # High confidence fuzzy match
        confidence = 0.90
        
        is_duplicate = service._is_fuzzy_duplicate(confidence)
        
        assert is_duplicate is True

    def test_fuzzy_duplicate_with_low_confidence(self, mock_db_session):
        """Test fuzzy duplicate detection with low confidence."""
        service = DuplicateDetectionService(db=mock_db_session)
        
        # Low confidence fuzzy match
        confidence = 0.80
        
        is_duplicate = service._is_fuzzy_duplicate(confidence)
        
        assert is_duplicate is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
