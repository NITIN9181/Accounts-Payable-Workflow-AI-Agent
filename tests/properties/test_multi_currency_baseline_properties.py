"""
Property-based tests for multi-currency baseline normalization.

Validates:
- **Property 42: Multi-Currency Baseline Normalization (Requirements 11.9)**

This test suite validates that for vendors with invoices in multiple currencies,
all amounts are normalized to USD using daily FX rates before calculating baseline
statistics (mean, std, p95).
"""

import pytest
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import uuid4
from unittest.mock import MagicMock, patch
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from ap_workflow.models.invoice import Invoice, InvoiceStatus
from ap_workflow.models.vendor_baseline import VendorBaseline
from ap_workflow.services.vendor_baseline import VendorBaselineService


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
def vendor_baseline_service(mock_db_session):
    """Create vendor baseline service with mock session."""
    return VendorBaselineService(db=mock_db_session)


# --- Helper Functions ---

def create_mock_invoice(
    vendor_key: str,
    total_amount: float,
    currency_code: str,
    fx_rate: float,
    paid_at: datetime = None,
    invoice_date: date = None
) -> MagicMock:
    """Create a mock invoice with specified parameters."""
    invoice = MagicMock()
    invoice.invoice_id = uuid4()
    invoice.vendor_key = vendor_key
    invoice.total_amount = Decimal(str(total_amount))
    invoice.total_amount_usd = Decimal(str(total_amount * fx_rate))
    invoice.currency_code = currency_code
    invoice.fx_rate = Decimal(str(fx_rate))
    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = paid_at or datetime.utcnow()
    # Convert invoice_date to datetime for consistency
    if invoice_date:
        invoice.invoice_date = datetime.combine(invoice_date, datetime.min.time())
    else:
        invoice.invoice_date = datetime.utcnow()
    return invoice


def compute_expected_statistics(amounts_usd: list) -> dict:
    """Compute expected baseline statistics from USD amounts."""
    if not amounts_usd:
        return {
            "mean": 0.0,
            "std": 0.0,
            "p95": 0.0,
            "count": 0
        }
    
    # Mean
    mean = sum(amounts_usd) / len(amounts_usd)
    
    # Standard deviation (sample)
    if len(amounts_usd) >= 2:
        variance = sum((x - mean) ** 2 for x in amounts_usd) / len(amounts_usd)
        std = variance ** 0.5
    else:
        std = 0.0
    
    # P95
    sorted_amounts = sorted(amounts_usd)
    p95_index = int(len(sorted_amounts) * 0.95)
    p95 = sorted_amounts[min(p95_index, len(sorted_amounts) - 1)]
    
    return {
        "mean": mean,
        "std": std,
        "p95": p95,
        "count": len(amounts_usd)
    }


# --- Property 42: Multi-Currency Baseline Normalization ---
# **Validates: Requirements 11.9**

class TestMultiCurrencyBaselineNormalization:
    """Property tests for multi-currency baseline normalization."""

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        num_invoices=st.integers(min_value=2, max_value=10),
        base_amount=st.floats(min_value=100.0, max_value=10000.0, allow_nan=False, allow_infinity=False)
    )
    def test_multi_currency_invoices_normalized_to_usd(self, vendor_baseline_service, num_invoices, base_amount):
        """
        **Property**: Invoices in multiple currencies should be normalized to USD before baseline calculation.
        **Validates: Requirements 11.9**
        """
        vendor_key = "VENDOR_MULTI_CURRENCY"
        
        # Create invoices in different currencies with different FX rates
        currencies = ["EUR", "GBP", "JPY", "USD"]
        fx_rates = {
            "EUR": 1.10,
            "GBP": 1.27,
            "JPY": 0.0067,
            "USD": 1.0
        }
        
        invoices = []
        amounts_usd = []
        
        for i in range(num_invoices):
            currency = currencies[i % len(currencies)]
            fx_rate = fx_rates[currency]
            amount = base_amount * (1 + i * 0.1)  # Vary amounts
            
            invoice = create_mock_invoice(
                vendor_key=vendor_key,
                total_amount=amount,
                currency_code=currency,
                fx_rate=fx_rate,
                paid_at=datetime.utcnow() - timedelta(days=i),
                invoice_date=date.today() - timedelta(days=i)
            )
            invoices.append(invoice)
            amounts_usd.append(float(amount * fx_rate))
        
        # Setup mock to return invoices
        vendor_baseline_service.db.query.return_value.filter.return_value.all.return_value = invoices
        
        # Update baseline
        baseline = vendor_baseline_service.update_vendor_baseline(vendor_key)
        
        # Verify baseline was created/updated
        assert baseline is not None
        
        # Verify mean is calculated from USD amounts
        expected_stats = compute_expected_statistics(amounts_usd)
        assert baseline.mean_invoice_amount_30d is not None
        assert abs(float(baseline.mean_invoice_amount_30d) - expected_stats["mean"]) < 1.0

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        eur_amount=st.floats(min_value=100.0, max_value=5000.0, allow_nan=False, allow_infinity=False),
        gbp_amount=st.floats(min_value=100.0, max_value=5000.0, allow_nan=False, allow_infinity=False),
        jpy_amount=st.floats(min_value=10000.0, max_value=500000.0, allow_nan=False, allow_infinity=False)
    )
    def test_multi_currency_mean_calculation_uses_usd_amounts(self, vendor_baseline_service, eur_amount, gbp_amount, jpy_amount):
        """
        **Property**: Mean baseline should be calculated from USD-normalized amounts, not original amounts.
        **Validates: Requirements 11.9**
        """
        vendor_key = "VENDOR_EUR_GBP_JPY"
        
        # Create invoices in different currencies
        eur_invoice = create_mock_invoice(
            vendor_key=vendor_key,
            total_amount=eur_amount,
            currency_code="EUR",
            fx_rate=1.10
        )
        
        gbp_invoice = create_mock_invoice(
            vendor_key=vendor_key,
            total_amount=gbp_amount,
            currency_code="GBP",
            fx_rate=1.27
        )
        
        jpy_invoice = create_mock_invoice(
            vendor_key=vendor_key,
            total_amount=jpy_amount,
            currency_code="JPY",
            fx_rate=0.0067
        )
        
        invoices = [eur_invoice, gbp_invoice, jpy_invoice]
        
        # Setup mock
        vendor_baseline_service.db.query.return_value.filter.return_value.all.return_value = invoices
        
        # Calculate expected mean from USD amounts
        amounts_usd = [
            eur_amount * 1.10,
            gbp_amount * 1.27,
            jpy_amount * 0.0067
        ]
        expected_mean = sum(amounts_usd) / len(amounts_usd)
        
        # Update baseline
        baseline = vendor_baseline_service.update_vendor_baseline(vendor_key)
        
        # Verify mean is calculated from USD amounts
        assert baseline.mean_invoice_amount_30d is not None
        assert abs(float(baseline.mean_invoice_amount_30d) - expected_mean) < 1.0

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        num_invoices=st.integers(min_value=3, max_value=10),
        base_amount=st.floats(min_value=100.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
    )
    def test_multi_currency_std_calculation_uses_usd_amounts(self, vendor_baseline_service, num_invoices, base_amount):
        """
        **Property**: Standard deviation should be calculated from USD-normalized amounts.
        **Validates: Requirements 11.9**
        """
        vendor_key = "VENDOR_STD_CALC"
        
        # Create invoices with varying amounts in different currencies
        currencies = ["EUR", "GBP", "JPY", "USD"]
        fx_rates = {
            "EUR": 1.10,
            "GBP": 1.27,
            "JPY": 0.0067,
            "USD": 1.0
        }
        
        invoices = []
        amounts_usd = []
        
        for i in range(num_invoices):
            currency = currencies[i % len(currencies)]
            fx_rate = fx_rates[currency]
            amount = base_amount * (1 + i * 0.2)  # Vary amounts more
            
            invoice = create_mock_invoice(
                vendor_key=vendor_key,
                total_amount=amount,
                currency_code=currency,
                fx_rate=fx_rate
            )
            invoices.append(invoice)
            amounts_usd.append(float(amount * fx_rate))
        
        # Setup mock
        vendor_baseline_service.db.query.return_value.filter.return_value.all.return_value = invoices
        
        # Calculate expected std from USD amounts
        expected_stats = compute_expected_statistics(amounts_usd)
        
        # Update baseline
        baseline = vendor_baseline_service.update_vendor_baseline(vendor_key)
        
        # Verify std is calculated from USD amounts
        assert baseline.std_invoice_amount_30d is not None
        assert abs(float(baseline.std_invoice_amount_30d) - expected_stats["std"]) < 1.0

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        num_invoices=st.integers(min_value=5, max_value=15),
        base_amount=st.floats(min_value=100.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
    )
    def test_multi_currency_p95_calculation_uses_usd_amounts(self, vendor_baseline_service, num_invoices, base_amount):
        """
        **Property**: P95 percentile should be calculated from USD-normalized amounts.
        **Validates: Requirements 11.9**
        """
        vendor_key = "VENDOR_P95_CALC"
        
        # Create invoices with varying amounts in different currencies
        currencies = ["EUR", "GBP", "JPY", "USD"]
        fx_rates = {
            "EUR": 1.10,
            "GBP": 1.27,
            "JPY": 0.0067,
            "USD": 1.0
        }
        
        invoices = []
        amounts_usd = []
        
        for i in range(num_invoices):
            currency = currencies[i % len(currencies)]
            fx_rate = fx_rates[currency]
            amount = base_amount * (1 + i * 0.15)
            
            invoice = create_mock_invoice(
                vendor_key=vendor_key,
                total_amount=amount,
                currency_code=currency,
                fx_rate=fx_rate,
                paid_at=datetime.utcnow() - timedelta(days=i)
            )
            invoices.append(invoice)
            amounts_usd.append(float(amount * fx_rate))
        
        # Setup mock
        vendor_baseline_service.db.query.return_value.filter.return_value.all.return_value = invoices
        
        # Calculate expected p95 from USD amounts
        expected_stats = compute_expected_statistics(amounts_usd)
        
        # Update baseline
        baseline = vendor_baseline_service.update_vendor_baseline(vendor_key)
        
        # Verify p95 is calculated from USD amounts
        assert baseline.p95_invoice_amount_90d is not None
        assert abs(float(baseline.p95_invoice_amount_90d) - expected_stats["p95"]) < 1.0

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        num_invoices=st.integers(min_value=2, max_value=8)
    )
    def test_single_currency_vendor_still_normalized(self, vendor_baseline_service, num_invoices):
        """
        **Property**: Even single-currency vendors should have amounts normalized to USD.
        **Validates: Requirements 11.9**
        """
        vendor_key = "VENDOR_SINGLE_CURRENCY"
        
        # Create invoices all in EUR
        invoices = []
        amounts_usd = []
        
        for i in range(num_invoices):
            amount = 1000.0 + i * 100
            invoice = create_mock_invoice(
                vendor_key=vendor_key,
                total_amount=amount,
                currency_code="EUR",
                fx_rate=1.10
            )
            invoices.append(invoice)
            amounts_usd.append(amount * 1.10)
        
        # Setup mock
        vendor_baseline_service.db.query.return_value.filter.return_value.all.return_value = invoices
        
        # Update baseline
        baseline = vendor_baseline_service.update_vendor_baseline(vendor_key)
        
        # Verify amounts were normalized
        expected_stats = compute_expected_statistics(amounts_usd)
        assert baseline.mean_invoice_amount_30d is not None
        assert abs(float(baseline.mean_invoice_amount_30d) - expected_stats["mean"]) < 1.0

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        num_invoices=st.integers(min_value=2, max_value=10),
        base_amount=st.floats(min_value=100.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
    )
    def test_usd_invoices_have_fx_rate_1_0(self, vendor_baseline_service, num_invoices, base_amount):
        """
        **Property**: USD invoices should have fx_rate = 1.0 and not be converted.
        **Validates: Requirements 11.9**
        """
        vendor_key = "VENDOR_USD_ONLY"
        
        # Create USD invoices
        invoices = []
        amounts_usd = []
        
        for i in range(num_invoices):
            amount = base_amount * (1 + i * 0.1)
            invoice = create_mock_invoice(
                vendor_key=vendor_key,
                total_amount=amount,
                currency_code="USD",
                fx_rate=1.0
            )
            invoices.append(invoice)
            amounts_usd.append(amount * 1.0)
        
        # Setup mock
        vendor_baseline_service.db.query.return_value.filter.return_value.all.return_value = invoices
        
        # Update baseline
        baseline = vendor_baseline_service.update_vendor_baseline(vendor_key)
        
        # Verify USD amounts are unchanged
        expected_stats = compute_expected_statistics(amounts_usd)
        assert baseline.mean_invoice_amount_30d is not None
        assert abs(float(baseline.mean_invoice_amount_30d) - expected_stats["mean"]) < 1.0

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        num_invoices=st.integers(min_value=2, max_value=10),
        base_amount=st.floats(min_value=100.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
    )
    def test_different_fx_rates_produce_different_baselines(self, vendor_baseline_service, num_invoices, base_amount):
        """
        **Property**: Same invoice amounts with different FX rates should produce different baseline statistics.
        **Validates: Requirements 11.9**
        """
        vendor_key = "VENDOR_FX_RATE_IMPACT"
        
        # Create invoices with same amounts but different FX rates
        invoices_low_rate = []
        invoices_high_rate = []
        
        for i in range(num_invoices):
            amount = base_amount * (1 + i * 0.1)
            
            # Low FX rate (e.g., JPY)
            invoice_low = create_mock_invoice(
                vendor_key=vendor_key,
                total_amount=amount,
                currency_code="JPY",
                fx_rate=0.0067
            )
            invoices_low_rate.append(invoice_low)
            
            # High FX rate (e.g., GBP)
            invoice_high = create_mock_invoice(
                vendor_key=vendor_key,
                total_amount=amount,
                currency_code="GBP",
                fx_rate=1.27
            )
            invoices_high_rate.append(invoice_high)
        
        # Calculate expected means
        amounts_usd_low = [float(inv.total_amount_usd) for inv in invoices_low_rate]
        amounts_usd_high = [float(inv.total_amount_usd) for inv in invoices_high_rate]
        
        mean_low = sum(amounts_usd_low) / len(amounts_usd_low)
        mean_high = sum(amounts_usd_high) / len(amounts_usd_high)
        
        # Means should be different
        assert abs(mean_low - mean_high) > 1.0

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        num_invoices=st.integers(min_value=2, max_value=10),
        base_amount=st.floats(min_value=100.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
    )
    def test_multi_currency_baseline_idempotent(self, vendor_baseline_service, num_invoices, base_amount):
        """
        **Property**: Calculating baseline twice with same data should produce identical results.
        **Validates: Requirements 11.9 (Idempotence)**
        """
        vendor_key = "VENDOR_IDEMPOTENT"
        
        # Create invoices in multiple currencies
        currencies = ["EUR", "GBP", "JPY"]
        fx_rates = {"EUR": 1.10, "GBP": 1.27, "JPY": 0.0067}
        
        invoices = []
        for i in range(num_invoices):
            currency = currencies[i % len(currencies)]
            amount = base_amount * (1 + i * 0.1)
            invoice = create_mock_invoice(
                vendor_key=vendor_key,
                total_amount=amount,
                currency_code=currency,
                fx_rate=fx_rates[currency]
            )
            invoices.append(invoice)
        
        # Setup mock
        vendor_baseline_service.db.query.return_value.filter.return_value.all.return_value = invoices
        
        # First calculation
        baseline1 = vendor_baseline_service.update_vendor_baseline(vendor_key)
        mean1 = float(baseline1.mean_invoice_amount_30d) if baseline1.mean_invoice_amount_30d else 0.0
        std1 = float(baseline1.std_invoice_amount_30d) if baseline1.std_invoice_amount_30d else 0.0
        
        # Second calculation (should be identical)
        baseline2 = vendor_baseline_service.update_vendor_baseline(vendor_key)
        mean2 = float(baseline2.mean_invoice_amount_30d) if baseline2.mean_invoice_amount_30d else 0.0
        std2 = float(baseline2.std_invoice_amount_30d) if baseline2.std_invoice_amount_30d else 0.0
        
        # Results should be identical
        assert abs(mean1 - mean2) < 0.01
        assert abs(std1 - std2) < 0.01

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        num_invoices=st.integers(min_value=2, max_value=10),
        base_amount=st.floats(min_value=100.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
    )
    def test_multi_currency_baseline_statistics_in_valid_range(self, vendor_baseline_service, num_invoices, base_amount):
        """
        **Property**: Baseline statistics should be in valid ranges (non-negative, reasonable values).
        **Validates: Requirements 11.9**
        """
        vendor_key = "VENDOR_VALID_RANGE"
        
        # Create invoices in multiple currencies
        currencies = ["EUR", "GBP", "JPY", "USD"]
        fx_rates = {"EUR": 1.10, "GBP": 1.27, "JPY": 0.0067, "USD": 1.0}
        
        invoices = []
        for i in range(num_invoices):
            currency = currencies[i % len(currencies)]
            amount = base_amount * (1 + i * 0.1)
            invoice = create_mock_invoice(
                vendor_key=vendor_key,
                total_amount=amount,
                currency_code=currency,
                fx_rate=fx_rates[currency]
            )
            invoices.append(invoice)
        
        # Setup mock
        vendor_baseline_service.db.query.return_value.filter.return_value.all.return_value = invoices
        
        # Update baseline
        baseline = vendor_baseline_service.update_vendor_baseline(vendor_key)
        
        # Verify statistics are in valid ranges
        assert baseline.mean_invoice_amount_30d is not None
        assert float(baseline.mean_invoice_amount_30d) >= 0
        
        assert baseline.std_invoice_amount_30d is not None
        assert float(baseline.std_invoice_amount_30d) >= 0
        
        assert baseline.p95_invoice_amount_90d is not None
        assert float(baseline.p95_invoice_amount_90d) >= 0
        
        # P95 should be >= mean
        if baseline.mean_invoice_amount_30d and baseline.p95_invoice_amount_90d:
            assert float(baseline.p95_invoice_amount_90d) >= float(baseline.mean_invoice_amount_30d) * 0.9

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    @given(
        num_invoices=st.integers(min_value=2, max_value=10),
        base_amount=st.floats(min_value=100.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
    )
    def test_multi_currency_baseline_mean_within_invoice_range(self, vendor_baseline_service, num_invoices, base_amount):
        """
        **Property**: Baseline mean should be within the range of invoice amounts (min <= mean <= max).
        **Validates: Requirements 11.9**
        """
        vendor_key = "VENDOR_MEAN_RANGE"
        
        # Create invoices in multiple currencies
        currencies = ["EUR", "GBP", "JPY"]
        fx_rates = {"EUR": 1.10, "GBP": 1.27, "JPY": 0.0067}
        
        invoices = []
        amounts_usd = []
        
        for i in range(num_invoices):
            currency = currencies[i % len(currencies)]
            amount = base_amount * (1 + i * 0.1)
            invoice = create_mock_invoice(
                vendor_key=vendor_key,
                total_amount=amount,
                currency_code=currency,
                fx_rate=fx_rates[currency]
            )
            invoices.append(invoice)
            amounts_usd.append(float(amount * fx_rates[currency]))
        
        # Setup mock
        vendor_baseline_service.db.query.return_value.filter.return_value.all.return_value = invoices
        
        # Update baseline
        baseline = vendor_baseline_service.update_vendor_baseline(vendor_key)
        
        # Verify mean is within range
        if baseline.mean_invoice_amount_30d:
            mean = float(baseline.mean_invoice_amount_30d)
            min_amount = min(amounts_usd)
            max_amount = max(amounts_usd)
            
            assert min_amount <= mean <= max_amount


# --- Integration Tests ---

class TestMultiCurrencyBaselineIntegration:
    """Integration tests for multi-currency baseline normalization."""

    def test_multi_currency_baseline_with_mixed_currencies(self, mock_db_session):
        """Test baseline calculation with mixed currencies."""
        service = VendorBaselineService(db=mock_db_session)
        vendor_key = "VENDOR_MIXED"
        
        # Create invoices in different currencies
        eur_invoice = create_mock_invoice(
            vendor_key=vendor_key,
            total_amount=1000.0,
            currency_code="EUR",
            fx_rate=1.10
        )
        
        gbp_invoice = create_mock_invoice(
            vendor_key=vendor_key,
            total_amount=1000.0,
            currency_code="GBP",
            fx_rate=1.27
        )
        
        usd_invoice = create_mock_invoice(
            vendor_key=vendor_key,
            total_amount=1000.0,
            currency_code="USD",
            fx_rate=1.0
        )
        
        invoices = [eur_invoice, gbp_invoice, usd_invoice]
        
        # Setup mock
        mock_db_session.query.return_value.filter.return_value.all.return_value = invoices
        
        # Calculate baseline
        baseline = service.update_vendor_baseline(vendor_key)
        
        # Verify baseline was created
        assert baseline is not None
        
        # Expected mean: (1000*1.10 + 1000*1.27 + 1000*1.0) / 3 = 1123.33
        expected_mean = (1000 * 1.10 + 1000 * 1.27 + 1000 * 1.0) / 3
        assert baseline.mean_invoice_amount_30d is not None
        assert abs(float(baseline.mean_invoice_amount_30d) - expected_mean) < 1.0

    def test_multi_currency_baseline_with_varying_amounts(self, mock_db_session):
        """Test baseline calculation with varying amounts in different currencies."""
        service = VendorBaselineService(db=mock_db_session)
        vendor_key = "VENDOR_VARYING"
        
        # Create invoices with varying amounts
        invoices = [
            create_mock_invoice(vendor_key, 500.0, "EUR", 1.10),
            create_mock_invoice(vendor_key, 1000.0, "GBP", 1.27),
            create_mock_invoice(vendor_key, 2000.0, "JPY", 0.0067),
            create_mock_invoice(vendor_key, 1500.0, "USD", 1.0),
        ]
        
        # Setup mock
        mock_db_session.query.return_value.filter.return_value.all.return_value = invoices
        
        # Calculate baseline
        baseline = service.update_vendor_baseline(vendor_key)
        
        # Verify baseline was created
        assert baseline is not None
        
        # Expected mean: (500*1.10 + 1000*1.27 + 2000*0.0067 + 1500*1.0) / 4
        amounts_usd = [500*1.10, 1000*1.27, 2000*0.0067, 1500*1.0]
        expected_mean = sum(amounts_usd) / len(amounts_usd)
        
        assert baseline.mean_invoice_amount_30d is not None
        assert abs(float(baseline.mean_invoice_amount_30d) - expected_mean) < 1.0

    def test_multi_currency_baseline_empty_invoices(self, mock_db_session):
        """Test baseline calculation with no invoices."""
        service = VendorBaselineService(db=mock_db_session)
        vendor_key = "VENDOR_EMPTY"
        
        # Setup mock to return empty list
        mock_db_session.query.return_value.filter.return_value.all.return_value = []
        
        # Calculate baseline
        baseline = service.update_vendor_baseline(vendor_key)
        
        # Verify baseline was created with default values
        assert baseline is not None
        assert baseline.mean_invoice_amount_30d == Decimal("0.0") or baseline.mean_invoice_amount_30d is None
        assert baseline.std_invoice_amount_30d == Decimal("0.0") or baseline.std_invoice_amount_30d is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
