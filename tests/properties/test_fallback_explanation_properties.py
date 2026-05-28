"""
Property-based tests for fallback explanation generation.

Validates:
- **Property 24: LLM Explanation Generation (Requirement 7.1)**
- **Property 27: Fallback Explanation Marking (Requirement 7.7)**
"""

import hashlib
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from ap_workflow.services.llm_explainer import LLMExplainerService
from ap_workflow.models.exception import InvoiceException, SeverityBand
from ap_workflow.models.llm_explanation import LLMExplanationCache
from ap_workflow.models.invoice import Invoice


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
def llm_explainer_service(mock_db_session):
    """Create LLM explainer service with mock session."""
    service = LLMExplainerService(db=mock_db_session)
    return service


# --- Helper Functions ---

def compute_cache_key(vendor_key: str, exception_type: str, exception_details: str) -> str:
    """Compute cache key for LLM explanation."""
    hash_input = f"{vendor_key}{exception_type}{exception_details}"
    return hashlib.sha256(hash_input.encode()).hexdigest()


# --- Property 24: LLM Explanation Generation ---
# **Validates: Requirement 7.1**
# Property: WHEN an invoice_exception is created with final_severity > 0.4, 
# THE LLM_Explainer SHALL attempt to generate a natural language explanation.
# WHEN the LLM is unavailable or rate limit is exceeded, THE System SHALL generate 
# a fallback explanation using a template.

class TestLLMExplanationGeneration:
    """Property tests for LLM explanation generation with fallback."""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        vendor_name=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Po'))),
        total_amount=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2),
        invoice_date=st.dates(min_value=datetime(2020, 1, 1).date(), max_value=datetime(2030, 12, 31).date()),
        mean_amount_30d=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2),
        exception_type=st.sampled_from(["DUPLICATE_EXACT", "DUPLICATE_FUZZY", "PO_MISMATCH", "PO_MISSING", "PARTIAL_RECEIPT", "RECEIPT_MISSING"])
    )
    def test_fallback_explanation_generated_when_unavailable(
        self, llm_explainer_service, vendor_name, total_amount, invoice_date, mean_amount_30d, exception_type
    ):
        """
        **Property**: Fallback explanation should be generated when LLM is unavailable.
        **Validates: Requirement 7.1**
        
        Requirement states: "WHEN the LLM is unavailable (timeout >10s, HTTP error, invalid response) 
        or rate limit is exceeded, THE System SHALL generate a fallback explanation using a template"
        """
        # Generate fallback explanation
        explanation = llm_explainer_service.generate_fallback_explanation(
            vendor_name=vendor_name,
            total_amount=total_amount,
            invoice_date=invoice_date,
            mean_amount_30d=mean_amount_30d,
            exception_type=exception_type
        )
        
        # Fallback explanation should be generated
        assert explanation is not None
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        
        # Should contain vendor name
        assert vendor_name in explanation
        
        # Should contain total amount
        assert str(total_amount) in explanation
        
        # Should contain invoice date
        assert str(invoice_date) in explanation
        
        # Should contain mean amount
        assert str(mean_amount_30d) in explanation
        
        # Should contain exception type
        assert exception_type in explanation

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        vendor_name=st.text(min_size=1, max_size=100),
        total_amount=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2),
        invoice_date=st.dates(),
        mean_amount_30d=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2),
        exception_type=st.text(min_size=1, max_size=50)
    )
    def test_fallback_explanation_contains_deviation_indicator(
        self, llm_explainer_service, vendor_name, total_amount, invoice_date, mean_amount_30d, exception_type
    ):
        """
        **Property**: Fallback explanation should indicate if amount is above or below average.
        **Validates: Requirement 7.1**
        
        Template format: "{vendor_name} invoiced ${total_amount} on {invoice_date}, 
        which is {deviation} the 30-day average of ${mean_amount_30d}. 
        Exception type: {exception_type}."
        """
        explanation = llm_explainer_service.generate_fallback_explanation(
            vendor_name=vendor_name,
            total_amount=total_amount,
            invoice_date=invoice_date,
            mean_amount_30d=mean_amount_30d,
            exception_type=exception_type
        )
        
        # Should contain "above" or "below" to indicate deviation
        assert "above" in explanation or "below" in explanation
        
        # If total_amount > mean_amount_30d, should say "above"
        if total_amount > mean_amount_30d:
            assert "above" in explanation
        
        # If total_amount < mean_amount_30d, should say "below"
        elif total_amount < mean_amount_30d:
            assert "below" in explanation

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        vendor_name=st.text(min_size=1, max_size=100),
        total_amount=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2),
        invoice_date=st.dates(),
        mean_amount_30d=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2),
        exception_type=st.text(min_size=1, max_size=50)
    )
    def test_fallback_explanation_format_matches_template(
        self, llm_explainer_service, vendor_name, total_amount, invoice_date, mean_amount_30d, exception_type
    ):
        """
        **Property**: Fallback explanation should match the required template format.
        **Validates: Requirement 7.1**
        
        Template: "{vendor_name} invoiced ${total_amount} on {invoice_date}, 
        which is {deviation} the 30-day average of ${mean_amount_30d}. 
        Exception type: {exception_type}."
        """
        explanation = llm_explainer_service.generate_fallback_explanation(
            vendor_name=vendor_name,
            total_amount=total_amount,
            invoice_date=invoice_date,
            mean_amount_30d=mean_amount_30d,
            exception_type=exception_type
        )
        
        # Should follow the template structure
        assert "invoiced $" in explanation
        assert "on" in explanation
        assert "which is" in explanation
        assert "the 30-day average of $" in explanation
        assert "Exception type:" in explanation
        
        # Should end with period
        assert explanation.endswith(".")

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        vendor_name=st.text(min_size=1, max_size=100),
        total_amount=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2),
        invoice_date=st.dates(),
        mean_amount_30d=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2),
        exception_type=st.text(min_size=1, max_size=50)
    )
    def test_fallback_explanation_deterministic(
        self, llm_explainer_service, vendor_name, total_amount, invoice_date, mean_amount_30d, exception_type
    ):
        """
        **Property**: Fallback explanation generation must be deterministic (idempotence).
        **Validates: Requirement 7.1**
        
        Requirement states: "Fallback explanations are deterministic and consistent"
        """
        # Generate explanation twice with same inputs
        explanation1 = llm_explainer_service.generate_fallback_explanation(
            vendor_name=vendor_name,
            total_amount=total_amount,
            invoice_date=invoice_date,
            mean_amount_30d=mean_amount_30d,
            exception_type=exception_type
        )
        
        explanation2 = llm_explainer_service.generate_fallback_explanation(
            vendor_name=vendor_name,
            total_amount=total_amount,
            invoice_date=invoice_date,
            mean_amount_30d=mean_amount_30d,
            exception_type=exception_type
        )
        
        # Explanations must be identical
        assert explanation1 == explanation2

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        vendor_key=st.text(min_size=1, max_size=100),
        exception_type=st.text(min_size=1, max_size=50),
        exception_details=st.text(min_size=0, max_size=500)
    )
    def test_cache_key_computation_deterministic(
        self, llm_explainer_service, vendor_key, exception_type, exception_details
    ):
        """
        **Property**: Cache key computation must be deterministic (idempotence).
        **Validates: Requirement 7.1**
        
        Cache keys must be consistent for the same inputs.
        """
        # Compute cache key twice
        key1 = llm_explainer_service.compute_cache_key(vendor_key, exception_type, exception_details)
        key2 = llm_explainer_service.compute_cache_key(vendor_key, exception_type, exception_details)
        
        # Keys must be identical
        assert key1 == key2
        
        # Should be valid SHA-256 hex (64 characters)
        assert len(key1) == 64
        assert all(c in '0123456789abcdef' for c in key1)

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        vendor_key=st.text(min_size=1, max_size=100),
        exception_type=st.text(min_size=1, max_size=50),
        exception_details1=st.text(min_size=0, max_size=500),
        exception_details2=st.text(min_size=0, max_size=500)
    )
    def test_different_inputs_produce_different_cache_keys(
        self, llm_explainer_service, vendor_key, exception_type, exception_details1, exception_details2
    ):
        """
        **Property**: Different inputs should produce different cache keys (collision resistance).
        **Validates: Requirement 7.1**
        
        This validates the collision resistance of SHA-256.
        """
        assume(exception_details1 != exception_details2)
        
        key1 = llm_explainer_service.compute_cache_key(vendor_key, exception_type, exception_details1)
        key2 = llm_explainer_service.compute_cache_key(vendor_key, exception_type, exception_details2)
        
        # Different inputs should produce different keys
        assert key1 != key2


# --- Property 27: Fallback Explanation Marking ---
# **Validates: Requirement 7.7**
# Property: WHEN a fallback explanation is used, THE System SHALL set 
# llm_explanation_fallback = true and include a note in the UI.
# Every exception with final_severity > 0.4 SHALL have either llm_explanation 
# or llm_explanation_fallback = true.

class TestFallbackExplanationMarking:
    """Property tests for fallback explanation marking."""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        vendor_key=st.text(min_size=1, max_size=100),
        exception_type=st.text(min_size=1, max_size=50),
        exception_details=st.text(min_size=0, max_size=500),
        vendor_name=st.text(min_size=1, max_size=100),
        total_amount=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2),
        invoice_date=st.dates(),
        mean_amount_30d=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2)
    )
    def test_fallback_explanation_sets_flag_true(
        self, llm_explainer_service, vendor_key, exception_type, exception_details,
        vendor_name, total_amount, invoice_date, mean_amount_30d
    ):
        """
        **Property**: When fallback explanation is generated, llm_explanation_fallback should be true.
        **Validates: Requirement 7.7**
        
        Requirement states: "WHEN a fallback explanation is used, THE System SHALL set 
        llm_explanation_fallback = true"
        """
        # Generate explanation (will be fallback since LLM is not called)
        explanation, is_fallback = llm_explainer_service.generate_explanation(
            exception_id=str(uuid.uuid4()),
            vendor_key=vendor_key,
            exception_type=exception_type,
            exception_details=exception_details,
            vendor_name=vendor_name,
            total_amount=total_amount,
            invoice_date=invoice_date,
            mean_amount_30d=mean_amount_30d
        )
        
        # Should return fallback flag as True
        assert is_fallback is True
        
        # Explanation should not be None
        assert explanation is not None

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        exception_id=st.just(str(uuid.uuid4())),
        vendor_key=st.text(min_size=1, max_size=100),
        exception_type=st.text(min_size=1, max_size=50),
        exception_details=st.text(min_size=0, max_size=500),
        vendor_name=st.text(min_size=1, max_size=100),
        total_amount=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2),
        invoice_date=st.dates(),
        mean_amount_30d=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2)
    )
    def test_exception_updated_with_fallback_flag(
        self, mock_db_session, exception_id, vendor_key, exception_type, exception_details,
        vendor_name, total_amount, invoice_date, mean_amount_30d
    ):
        """
        **Property**: Exception record should be updated with llm_explanation_fallback = true.
        **Validates: Requirement 7.7**
        
        Requirement states: "Every exception with final_severity > 0.4 SHALL have either 
        llm_explanation or llm_explanation_fallback = true"
        """
        service = LLMExplainerService(db=mock_db_session)
        
        # Create mock exception
        mock_exception = MagicMock(spec=InvoiceException)
        mock_exception.exception_id = exception_id
        mock_exception.vendor_key = vendor_key
        mock_exception.vendor_name = vendor_name
        mock_exception.total_amount_usd = total_amount
        mock_exception.total_amount = total_amount
        mock_exception.invoice_date = invoice_date
        mock_exception.exception_type = exception_type
        mock_exception.details_json = exception_details
        
        # Set up mock to return the exception
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_exception
        
        # Update exception with explanation
        result = service.update_exception_with_explanation(
            exception_id=exception_id,
            explanation="Test explanation",
            is_fallback=True
        )
        
        # Should have updated the exception
        assert mock_exception.llm_explanation == "Test explanation"
        assert mock_exception.llm_explanation_fallback is True
        assert mock_exception.llm_explanation_ready is True

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        vendor_key=st.text(min_size=1, max_size=100),
        exception_type=st.text(min_size=1, max_size=50),
        exception_details=st.text(min_size=0, max_size=500),
        vendor_name=st.text(min_size=1, max_size=100),
        total_amount=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2),
        invoice_date=st.dates(),
        mean_amount_30d=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2)
    )
    def test_fallback_explanation_always_has_flag(
        self, llm_explainer_service, vendor_key, exception_type, exception_details,
        vendor_name, total_amount, invoice_date, mean_amount_30d
    ):
        """
        **Property**: Fallback explanations should always have the flag set to true.
        **Validates: Requirement 7.7**
        
        This validates that the fallback flag is consistently set.
        """
        # Generate multiple fallback explanations
        for _ in range(5):
            explanation, is_fallback = llm_explainer_service.generate_explanation(
                exception_id=str(uuid.uuid4()),
                vendor_key=vendor_key,
                exception_type=exception_type,
                exception_details=exception_details,
                vendor_name=vendor_name,
                total_amount=total_amount,
                invoice_date=invoice_date,
                mean_amount_30d=mean_amount_30d
            )
            
            # All should be marked as fallback
            assert is_fallback is True

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        vendor_key=st.text(min_size=1, max_size=100),
        exception_type=st.text(min_size=1, max_size=50),
        exception_details=st.text(min_size=0, max_size=500),
        vendor_name=st.text(min_size=1, max_size=100),
        total_amount=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2),
        invoice_date=st.dates(),
        mean_amount_30d=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2)
    )
    def test_cached_explanation_preserves_fallback_flag(
        self, llm_explainer_service, vendor_key, exception_type, exception_details,
        vendor_name, total_amount, invoice_date, mean_amount_30d
    ):
        """
        **Property**: Cached fallback explanations should preserve the fallback flag.
        **Validates: Requirement 7.7**
        
        When an explanation is cached and retrieved, the fallback flag should be preserved.
        """
        # Generate first explanation (will be cached)
        explanation1, is_fallback1 = llm_explainer_service.generate_explanation(
            exception_id=str(uuid.uuid4()),
            vendor_key=vendor_key,
            exception_type=exception_type,
            exception_details=exception_details,
            vendor_name=vendor_name,
            total_amount=total_amount,
            invoice_date=invoice_date,
            mean_amount_30d=mean_amount_30d
        )
        
        # Generate second explanation with same inputs (should be cached)
        explanation2, is_fallback2 = llm_explainer_service.generate_explanation(
            exception_id=str(uuid.uuid4()),
            vendor_key=vendor_key,
            exception_type=exception_type,
            exception_details=exception_details,
            vendor_name=vendor_name,
            total_amount=total_amount,
            invoice_date=invoice_date,
            mean_amount_30d=mean_amount_30d
        )
        
        # Both should be marked as fallback
        assert is_fallback1 is True
        assert is_fallback2 is True
        
        # Explanations should be identical (from cache)
        assert explanation1 == explanation2

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        vendor_key=st.text(min_size=1, max_size=100),
        exception_type=st.text(min_size=1, max_size=50),
        exception_details=st.text(min_size=0, max_size=500),
        vendor_name=st.text(min_size=1, max_size=100),
        total_amount=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2),
        invoice_date=st.dates(),
        mean_amount_30d=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2)
    )
    def test_fallback_explanation_not_empty(
        self, llm_explainer_service, vendor_key, exception_type, exception_details,
        vendor_name, total_amount, invoice_date, mean_amount_30d
    ):
        """
        **Property**: Fallback explanations should never be empty.
        **Validates: Requirement 7.7**
        
        Every fallback explanation must contain meaningful content.
        """
        explanation, is_fallback = llm_explainer_service.generate_explanation(
            exception_id=str(uuid.uuid4()),
            vendor_key=vendor_key,
            exception_type=exception_type,
            exception_details=exception_details,
            vendor_name=vendor_name,
            total_amount=total_amount,
            invoice_date=invoice_date,
            mean_amount_30d=mean_amount_30d
        )
        
        # Explanation should not be empty
        assert explanation is not None
        assert len(explanation) > 0
        assert explanation.strip() != ""

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        vendor_key=st.text(min_size=1, max_size=100),
        exception_type=st.text(min_size=1, max_size=50),
        exception_details=st.text(min_size=0, max_size=500),
        vendor_name=st.text(min_size=1, max_size=100),
        total_amount=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2),
        invoice_date=st.dates(),
        mean_amount_30d=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2)
    )
    def test_fallback_explanation_contains_all_required_fields(
        self, llm_explainer_service, vendor_key, exception_type, exception_details,
        vendor_name, total_amount, invoice_date, mean_amount_30d
    ):
        """
        **Property**: Fallback explanation should contain all required template fields.
        **Validates: Requirement 7.7**
        
        Template requires: vendor_name, total_amount, invoice_date, mean_amount_30d, exception_type
        """
        explanation, is_fallback = llm_explainer_service.generate_explanation(
            exception_id=str(uuid.uuid4()),
            vendor_key=vendor_key,
            exception_type=exception_type,
            exception_details=exception_details,
            vendor_name=vendor_name,
            total_amount=total_amount,
            invoice_date=invoice_date,
            mean_amount_30d=mean_amount_30d
        )
        
        # Should contain all required fields
        assert vendor_name in explanation
        assert str(total_amount) in explanation
        assert str(invoice_date) in explanation
        assert str(mean_amount_30d) in explanation
        assert exception_type in explanation

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        vendor_key=st.text(min_size=1, max_size=100),
        exception_type=st.text(min_size=1, max_size=50),
        exception_details=st.text(min_size=0, max_size=500),
        vendor_name=st.text(min_size=1, max_size=100),
        total_amount=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2),
        invoice_date=st.dates(),
        mean_amount_30d=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999999.99"), places=2)
    )
    def test_fallback_explanation_idempotent_with_flag(
        self, llm_explainer_service, vendor_key, exception_type, exception_details,
        vendor_name, total_amount, invoice_date, mean_amount_30d
    ):
        """
        **Property**: Fallback explanation generation should be idempotent (same inputs = same output + flag).
        **Validates: Requirement 7.7**
        
        Requirement states: "Fallback explanations are deterministic and consistent"
        """
        # Generate explanation multiple times
        results = []
        for _ in range(3):
            explanation, is_fallback = llm_explainer_service.generate_explanation(
                exception_id=str(uuid.uuid4()),
                vendor_key=vendor_key,
                exception_type=exception_type,
                exception_details=exception_details,
                vendor_name=vendor_name,
                total_amount=total_amount,
                invoice_date=invoice_date,
                mean_amount_30d=mean_amount_30d
            )
            results.append((explanation, is_fallback))
        
        # All results should be identical
        for i in range(1, len(results)):
            assert results[i][0] == results[0][0], "Explanations should be identical"
            assert results[i][1] == results[0][1], "Fallback flags should be identical"
            assert results[i][1] is True, "All should be marked as fallback"
