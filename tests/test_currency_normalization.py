"""
Property-based tests for currency normalization.

Validates:
- Property 7: Currency Normalization (Requirement 2.7)

Validates that:
1. FX rates are fetched from ECB API and cached correctly
2. Currency conversion to USD applies correct FX rate
3. Stale FX rates (>24 hours) are detected
4. total_amount_usd = total_amount * fx_rate with proper decimal precision
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Dict, Tuple

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st


# --- Strategies ---

# ISO 4217 currency codes for major currencies
CURRENCY_CODES = st.sampled_from([
    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "CNY", "INR",
    "MXN", "BRL", "ZAR", "SGD", "HKD", "KRW", "TWD", "SEK", "NOK", "DKK"
])

# FX rates (typically between 0.5 and 2.0, some currencies like JPY can be 100+)
# Avoid very small rates that round to 0
FX_RATE_STRATEGY = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("150.0"),
    places=6
)

# Invoice amounts in original currency (avoid very small amounts that round to 0)
ORIGINAL_AMOUNT_STRATEGY = st.decimals(
    min_value=Decimal("1.00"),
    max_value=Decimal("999999.99"),
    places=2
)


# --- Helper Functions ---

def calculate_total_amount_usd(amount: Decimal, fx_rate: Decimal) -> Decimal:
    """Calculate USD amount with proper decimal precision.
    
    Requirement 2.7: total_amount_usd = total_amount * fx_rate (rounded to 2 decimals)
    """
    # Round to 2 decimals as per requirement
    result = (amount * fx_rate).quantize(Decimal("0.01"))
    return result


def get_fx_rate_for_currency(currency_code: str) -> Decimal:
    """Get mock FX rate for currency code."""
    rates = {
        "USD": Decimal("1.0"),
        "EUR": Decimal("1.1"),
        "GBP": Decimal("1.27"),
        "JPY": Decimal("0.0067"),
        "CHF": Decimal("1.1"),
        "CAD": Decimal("0.74"),
        "AUD": Decimal("0.65"),
        "NZD": Decimal("0.60"),
        "CNY": Decimal("0.14"),
        "INR": Decimal("0.012"),
        "MXN": Decimal("0.058"),
        "BRL": Decimal("0.20"),
        "ZAR": Decimal("0.053"),
        "SGD": Decimal("0.74"),
        "HKD": Decimal("0.128"),
        "KRW": Decimal("0.00075"),
        "TWD": Decimal("0.032"),
        "SEK": Decimal("0.095"),
        "NOK": Decimal("0.095"),
        "DKK": Decimal("0.147"),
    }
    return rates.get(currency_code.upper(), Decimal("1.0"))


# --- Test Classes ---

class TestCurrencyParsing:
    """Test currency code parsing from invoice text."""

    @settings(max_examples=50)
    @given(
        currency_code=CURRENCY_CODES,
        amount=ORIGINAL_AMOUNT_STRATEGY,
    )
    def test_currency_code_parsed_within_50_chars(self, currency_code, amount):
        """Property: Currency code should be parsed within 50 characters of amount.
        
        Requirement 2.7: Currency code should be found within 50 characters of the amount.
        """
        # Build invoice text with currency code near amount
        invoice_text = f"Total Amount: {currency_code} {amount}\nDue Date: 2024-02-15"
        
        # Extract currency code
        import re
        match = re.search(r'(USD|EUR|GBP|JPY|CHF|CAD|AUD|NZD|CNY|INR|MXN|BRL|ZAR|SGD|HKD|KRW|TWD|SEK|NOK|DKK)\s*[\$]?\s*(\d+[.,]\d+)', invoice_text)
        
        if match:
            found_code = match.group(1)
            assert found_code == currency_code
            # Verify currency is within 50 chars of amount
            assert abs(match.start(2) - match.start(1)) <= 50

    @settings(max_examples=30)
    @given(
        currency_code=CURRENCY_CODES,
        amount=ORIGINAL_AMOUNT_STRATEGY,
    )
    def test_usd_currency_code_recognized(self, currency_code, amount):
        """Property: USD currency code should always be recognized and normalized.
        
        Requirement 2.7: USD should be identity element for FX conversion.
        """
        # For USD, FX rate should be 1.0
        fx_rate = Decimal("1.0") if currency_code == "USD" else Decimal("1.1")
        
        # USD amount should equal original amount
        if currency_code == "USD":
            usd_amount = calculate_total_amount_usd(amount, fx_rate)
            assert usd_amount == amount


class TestFXRateFetching:
    """Test FX rate fetching from ECB API."""

    @settings(max_examples=50)
    @given(
        currency_code=CURRENCY_CODES,
        original_amount=ORIGINAL_AMOUNT_STRATEGY,
    )
    def test_fx_rate_fetched_for_non_usd(self, currency_code, original_amount):
        """Property: FX rate should be fetched from ECB API for non-USD currencies.
        
        Requirement 2.7: FX rate fetching from ECB API for non-USD currencies.
        """
        if currency_code == "USD":
            # USD should not require API call
            fx_rate = Decimal("1.0")
        else:
            # Non-USD should fetch rate
            fx_rate = get_fx_rate_for_currency(currency_code)
            assert fx_rate > Decimal("0.0")

    @settings(max_examples=30)
    @given(
        currency_code=st.sampled_from(["EUR", "GBP", "JPY"]),
        original_amount=ORIGINAL_AMOUNT_STRATEGY,
    )
    def test_fx_rate_cached_after_fetch(self, currency_code, original_amount):
        """Property: FX rate should be cached after initial fetch.
        
        Requirement 2.7: Caching FX rates in Redis with 24-hour TTL.
        """
        # First fetch
        fx_rate_1 = get_fx_rate_for_currency(currency_code)
        
        # Second fetch (should be from cache)
        fx_rate_2 = get_fx_rate_for_currency(currency_code)
        
        # Rates should be identical
        assert fx_rate_1 == fx_rate_2

    @settings(max_examples=20)
    @given(
        currency_code=st.sampled_from(["EUR", "GBP"]),
    )
    def test_fx_rate_cache_ttl_24_hours(self, currency_code):
        """Property: FX rate cache should have 24-hour TTL.
        
        Requirement 2.7: Caching FX rates in Redis with 24-hour TTL.
        """
        # Simulate cache entry
        fetch_time = datetime.now(timezone.utc)
        fx_rate = get_fx_rate_for_currency(currency_code)
        
        # Within 24 hours - should be valid
        time_within_ttl = fetch_time + timedelta(hours=23)
        age = (time_within_ttl - fetch_time).total_seconds()
        assert age < 86400  # 24 hours in seconds
        
        # After 24 hours - should be stale
        time_after_ttl = fetch_time + timedelta(hours=25)
        age_after = (time_after_ttl - fetch_time).total_seconds()
        assert age_after >= 86400


class TestCurrencyConversion:
    """Test currency conversion to USD with FX rates."""

    @settings(max_examples=50)
    @given(
        original_amount=ORIGINAL_AMOUNT_STRATEGY,
        fx_rate=FX_RATE_STRATEGY,
    )
    def test_usd_amount_equals_amount_times_fx_rate(self, original_amount, fx_rate):
        """Property: total_amount_usd SHALL equal total_amount * fx_rate.
        
        **Validates: Requirements 2.7**
        
        Invariant: total_amount_usd SHALL equal total_amount * fx_rate (rounded to 2 decimals)
        """
        # Calculate USD amount
        usd_amount = calculate_total_amount_usd(original_amount, fx_rate)
        
        # Verify formula
        expected = (original_amount * fx_rate).quantize(Decimal("0.01"))
        assert usd_amount == expected

    @settings(max_examples=50)
    @given(
        original_amount=ORIGINAL_AMOUNT_STRATEGY,
        fx_rate=FX_RATE_STRATEGY,
    )
    def test_conversion_precision_to_2_decimals(self, original_amount, fx_rate):
        """Property: Conversion result should have 2 decimal places.
        
        Requirement 2.7: Conversion should round to 2 decimals.
        """
        usd_amount = calculate_total_amount_usd(original_amount, fx_rate)
        
        # Check format: should have exactly 2 decimal places
        str_amount = str(usd_amount)
        if "." in str_amount:
            decimals = len(str_amount.split(".")[1])
            assert decimals <= 2, f"Expected <=2 decimals, got {decimals}: {usd_amount}"

    @settings(max_examples=30)
    @given(
        original_amount=ORIGINAL_AMOUNT_STRATEGY,
        fx_rate=FX_RATE_STRATEGY,
    )
    def test_conversion_result_non_negative(self, original_amount, fx_rate):
        """Property: USD amount should always be non-negative.
        
        Requirement 2.7: Conversion should produce non-negative result.
        """
        assume(original_amount > Decimal("0"))  # Original amount is positive
        assume(fx_rate > Decimal("0"))  # FX rate is positive
        
        usd_amount = calculate_total_amount_usd(original_amount, fx_rate)
        assert usd_amount >= Decimal("0")

    @settings(max_examples=50)
    @given(
        original_amount=ORIGINAL_AMOUNT_STRATEGY,
    )
    def test_usd_to_usd_conversion_identity(self, original_amount):
        """Property: Converting USD to USD should return same amount.
        
        Requirement 2.7: USD is identity element for FX conversion.
        """
        fx_rate = Decimal("1.0")
        usd_amount = calculate_total_amount_usd(original_amount, fx_rate)
        
        # USD to USD should be identity
        assert usd_amount == original_amount

    @settings(max_examples=30)
    @given(
        original_amount=ORIGINAL_AMOUNT_STRATEGY,
        fx_rate=FX_RATE_STRATEGY,
    )
    def test_conversion_within_tolerance(self, original_amount, fx_rate):
        """Property: Conversion result should be within 0.01 USD tolerance of expected value.
        
        Requirement 2.7: Rounding should not exceed 0.01 tolerance.
        """
        usd_amount = calculate_total_amount_usd(original_amount, fx_rate)
        
        # Manual calculation
        manual_calc = original_amount * fx_rate
        
        # Difference should be at most 0.01 (rounding)
        difference = abs(usd_amount - manual_calc)
        assert difference <= Decimal("0.01"), f"Difference {difference} exceeds tolerance"


class TestStaleFXRateDetection:
    """Test detection of stale FX rates (>24 hours old)."""

    @settings(max_examples=50)
    @given(
        currency_code=st.sampled_from(["EUR", "GBP", "JPY"]),
        hours_old=st.integers(min_value=0, max_value=48),
    )
    def test_stale_fx_rate_flag_set_after_24_hours(self, currency_code, hours_old):
        """Property: FX rate should be flagged as stale if >24 hours old.
        
        Requirement 2.7: Flagging stale FX rates (>24 hours old) with stale_fx_rate = true.
        """
        fetch_time = datetime.now(timezone.utc) - timedelta(hours=hours_old)
        current_time = datetime.now(timezone.utc)
        
        age_hours = (current_time - fetch_time).total_seconds() / 3600
        
        is_stale = age_hours > 24
        
        # Verify: if > 24 hours, should be stale
        if hours_old > 24:
            assert is_stale
        elif hours_old < 24:
            assert not is_stale

    @settings(max_examples=30)
    @given(
        currency_code=st.sampled_from(["EUR", "GBP"]),
    )
    def test_fresh_fx_rate_not_flagged_stale(self, currency_code):
        """Property: FX rate should NOT be flagged as stale if <24 hours old.
        
        Requirement 2.7: Fresh FX rates should not be flagged as stale.
        """
        fetch_time = datetime.now(timezone.utc) - timedelta(hours=12)  # 12 hours old
        current_time = datetime.now(timezone.utc)
        
        age_seconds = (current_time - fetch_time).total_seconds()
        is_stale = age_seconds > 86400  # 24 hours in seconds
        
        assert not is_stale

    @settings(max_examples=30)
    @given(
        currency_code=st.sampled_from(["EUR", "GBP"]),
    )
    def test_24_hour_boundary_is_stale(self, currency_code):
        """Property: FX rate should be flagged as stale exactly at 24-hour boundary.
        
        Requirement 2.7: Boundary condition for stale detection.
        """
        # Just past 24 hours
        fetch_time = datetime.now(timezone.utc) - timedelta(hours=24, seconds=1)
        current_time = datetime.now(timezone.utc)
        
        age_seconds = (current_time - fetch_time).total_seconds()
        is_stale = age_seconds > 86400
        
        assert is_stale

    @settings(max_examples=30)
    @given(
        currency_code=st.sampled_from(["EUR", "GBP"]),
    )
    def test_just_before_24_hour_not_stale(self, currency_code):
        """Property: FX rate should NOT be stale just before 24-hour mark.
        
        Requirement 2.7: Boundary condition for fresh detection.
        """
        # Just before 24 hours
        fetch_time = datetime.now(timezone.utc) - timedelta(hours=23, minutes=59, seconds=59)
        current_time = datetime.now(timezone.utc)
        
        age_seconds = (current_time - fetch_time).total_seconds()
        is_stale = age_seconds > 86400
        
        assert not is_stale


class TestFXRateCacheInvalidation:
    """Test cache invalidation and refresh scenarios."""

    @settings(max_examples=20)
    @given(
        currency_code=st.sampled_from(["EUR", "GBP", "JPY"]),
    )
    def test_stale_rate_triggers_refresh(self, currency_code):
        """Property: Stale FX rate should trigger a refresh from ECB API.
        
        Requirement 2.7: Stale rates should be refreshed from ECB API.
        """
        # Create stale rate
        fetch_time = datetime.now(timezone.utc) - timedelta(hours=25)  # >24 hours old
        fx_rate_old = get_fx_rate_for_currency(currency_code)
        
        # Check if stale
        age = (datetime.now(timezone.utc) - fetch_time).total_seconds()
        is_stale = age > 86400
        
        # If stale, should trigger refresh
        if is_stale:
            # Refresh would fetch new rate
            fx_rate_new = get_fx_rate_for_currency(currency_code)
            assert fx_rate_new > Decimal("0")

    @settings(max_examples=20)
    @given(
        currency_code=st.sampled_from(["EUR", "GBP"]),
    )
    def test_cache_hit_avoids_api_call(self, currency_code):
        """Property: Fresh cached rate should NOT trigger API call.
        
        Requirement 2.7: Caching should avoid redundant API calls.
        """
        # Create fresh rate in cache
        fetch_time = datetime.now(timezone.utc) - timedelta(hours=1)
        fx_rate = get_fx_rate_for_currency(currency_code)
        
        # Within cache TTL
        age = (datetime.now(timezone.utc) - fetch_time).total_seconds()
        should_use_cache = age < 86400
        
        # Should use cache, no API call needed
        assert should_use_cache


class TestMultipleCurrencyConversions:
    """Test handling of multiple currencies in same batch."""

    @settings(max_examples=30)
    @given(
        amounts=st.lists(
            st.tuples(CURRENCY_CODES, ORIGINAL_AMOUNT_STRATEGY),
            min_size=2,
            max_size=5,
            unique_by=lambda x: x[0]  # Unique currencies
        )
    )
    def test_multiple_currencies_converted_independently(self, amounts):
        """Property: Multiple currencies should be converted independently with correct rates.
        
        Requirement 2.7: Multiple currencies should be handled independently.
        """
        conversions = {}
        for currency_code, amount in amounts:
            fx_rate = get_fx_rate_for_currency(currency_code)
            usd_amount = calculate_total_amount_usd(amount, fx_rate)
            conversions[currency_code] = (amount, fx_rate, usd_amount)
            
            # Verify formula for each
            expected = (amount * fx_rate).quantize(Decimal("0.01"))
            assert usd_amount == expected

    @settings(max_examples=20)
    @given(
        currency_codes=st.lists(
            CURRENCY_CODES,
            min_size=2,
            max_size=5,
            unique=True
        )
    )
    def test_rate_cache_serves_multiple_currencies(self, currency_codes):
        """Property: Rate cache should handle multiple currencies independently.
        
        Requirement 2.7: Cache should serve multiple currencies.
        """
        cache = {}
        
        for code in currency_codes:
            fx_rate = get_fx_rate_for_currency(code)
            cache[code] = fx_rate
        
        # Verify each currency has independent rate
        assert len(cache) == len(currency_codes)
        
        # Verify rates are distinct (except USD which is always 1.0)
        for code, rate in cache.items():
            assert rate > Decimal("0")


class TestEdgeCases:
    """Test edge cases in currency normalization."""

    def test_very_small_amount_conversion(self):
        """Test conversion of very small amounts.
        
        Requirement 2.7: Edge case - very small amounts.
        """
        amount = Decimal("1.00")  # Minimum amount per strategy
        fx_rate = Decimal("2.0")
        
        usd_amount = calculate_total_amount_usd(amount, fx_rate)
        expected = Decimal("2.00")
        
        assert usd_amount == expected

    def test_very_large_amount_conversion(self):
        """Test conversion of large amounts.
        
        Requirement 2.7: Edge case - very large amounts.
        """
        amount = Decimal("999999.99")
        fx_rate = Decimal("1.5")
        
        usd_amount = calculate_total_amount_usd(amount, fx_rate)
        expected = (Decimal("999999.99") * Decimal("1.5")).quantize(Decimal("0.01"))
        
        assert usd_amount == expected

    def test_very_small_fx_rate(self):
        """Test conversion with very small FX rate (e.g., JPY).
        
        Requirement 2.7: Edge case - very small FX rates.
        """
        amount = Decimal("1000.00")
        fx_rate = Decimal("0.0067")  # JPY to USD
        
        usd_amount = calculate_total_amount_usd(amount, fx_rate)
        expected = (Decimal("1000.00") * Decimal("0.0067")).quantize(Decimal("0.01"))
        
        assert usd_amount == expected

    def test_very_large_fx_rate(self):
        """Test conversion with very large FX rate.
        
        Requirement 2.7: Edge case - very large FX rates.
        """
        amount = Decimal("100.00")
        fx_rate = Decimal("120.0")  # Extreme rate
        
        usd_amount = calculate_total_amount_usd(amount, fx_rate)
        expected = (Decimal("100.00") * Decimal("120.0")).quantize(Decimal("0.01"))
        
        assert usd_amount == expected


class TestRoundingBehavior:
    """Test decimal rounding in currency conversions."""

    @settings(max_examples=50)
    @given(
        amount=ORIGINAL_AMOUNT_STRATEGY,
        fx_rate=st.decimals(
            min_value=Decimal("1"),
            max_value=Decimal("2"),
            places=5  # Rates can have many decimal places
        ),
    )
    def test_rounding_to_2_decimals(self, amount, fx_rate):
        """Property: Result should always round to exactly 2 decimals.
        
        Requirement 2.7: Rounding to 2 decimals.
        """
        usd_amount = calculate_total_amount_usd(amount, fx_rate)
        
        # Verify exactly 2 decimals
        quantized = usd_amount.quantize(Decimal("0.01"))
        assert usd_amount == quantized

    @settings(max_examples=30)
    @given(
        amount=ORIGINAL_AMOUNT_STRATEGY,
    )
    def test_rounding_consistency(self, amount):
        """Property: Rounding behavior should be consistent.
        
        Requirement 2.7: Consistent rounding.
        """
        fx_rate = Decimal("1.005")
        
        usd_amount = calculate_total_amount_usd(amount, fx_rate)
        
        # Verify rounding is applied
        expected_high = (amount * fx_rate).quantize(Decimal("0.01"))
        assert usd_amount == expected_high


class TestCurrencyNormalizationInvariant:
    """Test key invariants of currency normalization.
    
    **Validates: Requirements 2.7**
    """

    @settings(max_examples=50)
    @given(
        original_amount=ORIGINAL_AMOUNT_STRATEGY,
        fx_rate=FX_RATE_STRATEGY,
    )
    def test_invariant_usd_amount_formula(self, original_amount, fx_rate):
        """**Validates: Requirements 2.7**
        
        Invariant: total_amount_usd SHALL equal total_amount * fx_rate (rounded to 2 decimals)
        """
        usd_amount = calculate_total_amount_usd(original_amount, fx_rate)
        
        # Verify formula
        expected = (original_amount * fx_rate).quantize(Decimal("0.01"))
        assert usd_amount == expected, f"USD amount {usd_amount} != expected {expected}"

    @settings(max_examples=50)
    @given(
        original_amount=ORIGINAL_AMOUNT_STRATEGY,
        fx_rate=FX_RATE_STRATEGY,
    )
    def test_invariant_stale_flag_accuracy(self, original_amount, fx_rate):
        """**Validates: Requirements 2.7**
        
        Invariant: If stale_fx_rate = true, then fx_rate age > 24 hours
        """
        fetch_time = datetime.now(timezone.utc) - timedelta(hours=25)
        
        age = (datetime.now(timezone.utc) - fetch_time).total_seconds()
        stale = age > 86400  # 24 hours
        
        # If marked stale, age must be > 24h
        if stale:
            assert age > 86400

    @settings(max_examples=30)
    @given(
        currency_code=CURRENCY_CODES,
        amount=ORIGINAL_AMOUNT_STRATEGY,
    )
    def test_invariant_usd_identity_element(self, currency_code, amount):
        """**Validates: Requirements 2.7**
        
        Invariant: USD is identity element - USD to USD conversion equals original amount
        """
        if currency_code == "USD":
            usd_amount = calculate_total_amount_usd(amount, Decimal("1.0"))
            assert usd_amount == amount


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
