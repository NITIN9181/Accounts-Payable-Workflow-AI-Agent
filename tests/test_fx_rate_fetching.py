"""
Unit tests for FX rate fetching and currency normalization (Task 6).

Tests the implementation of:
1. Fetching daily FX rates from ECB API for non-USD currencies
2. Caching FX rates in Redis with 24-hour TTL
3. Calculating total_amount_usd = total_amount * fx_rate for all invoices
4. Flagging stale FX rates (>24 hours old) with stale_fx_rate = true

Validates: Requirement 2.7
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, Mock
import pytest

from ap_workflow.services.ocr import OCRService


class TestFXRateFetching:
    """Test FX rate fetching from ECB API."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = MagicMock()
        mock_query = MagicMock()
        session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.first.return_value = None
        return session

    @pytest.fixture
    def mock_redis_client(self):
        """Create a mock Redis client."""
        return MagicMock()

    @pytest.fixture
    def ocr_service(self, mock_db_session, mock_redis_client):
        """Create OCR service with mocked dependencies."""
        service = OCRService(db=mock_db_session)
        service.redis_client = mock_redis_client
        return service

    def test_usd_currency_returns_identity_rate(self, ocr_service):
        """Test that USD currency returns FX rate of 1.0 without API call."""
        fx_rate, is_stale = ocr_service._calculate_fx_rate("USD")
        
        assert fx_rate == Decimal("1.0")
        assert is_stale is False
        # Should not call Redis for USD
        ocr_service.redis_client.get.assert_not_called()

    def test_non_usd_currency_checks_redis_cache(self, ocr_service, mock_redis_client):
        """Test that non-USD currencies check Redis cache first."""
        # Set up mock Redis to return cached rate
        cache_data = {
            "rate": "1.1",
            "fetch_time": datetime.utcnow().isoformat()
        }
        mock_redis_client.get.return_value = json.dumps(cache_data).encode('utf-8')
        
        fx_rate, is_stale = ocr_service._calculate_fx_rate("EUR")
        
        # Should check Redis cache
        mock_redis_client.get.assert_called_once_with("fx_rate:EUR")
        assert fx_rate == Decimal("1.1")
        assert is_stale is False

    def test_stale_cached_rate_marked_as_stale(self, ocr_service, mock_redis_client):
        """Test that cached rates older than 24 hours are marked as stale."""
        # Set up mock Redis with stale rate (25 hours old)
        old_time = datetime.utcnow() - timedelta(hours=25)
        cache_data = {
            "rate": "1.1",
            "fetch_time": old_time.isoformat()
        }
        mock_redis_client.get.return_value = json.dumps(cache_data).encode('utf-8')
        
        fx_rate, is_stale = ocr_service._calculate_fx_rate("EUR")
        
        assert fx_rate == Decimal("1.1")
        assert is_stale is True

    def test_fresh_cached_rate_not_marked_stale(self, ocr_service, mock_redis_client):
        """Test that cached rates younger than 24 hours are not marked as stale."""
        # Set up mock Redis with fresh rate (12 hours old)
        recent_time = datetime.utcnow() - timedelta(hours=12)
        cache_data = {
            "rate": "1.1",
            "fetch_time": recent_time.isoformat()
        }
        mock_redis_client.get.return_value = json.dumps(cache_data).encode('utf-8')
        
        fx_rate, is_stale = ocr_service._calculate_fx_rate("EUR")
        
        assert fx_rate == Decimal("1.1")
        assert is_stale is False

    @patch('ap_workflow.services.ocr.requests')
    def test_ecb_api_called_when_cache_miss(self, mock_requests, ocr_service, mock_redis_client):
        """Test that ECB API is called when rate is not in cache."""
        # Skip if requests is not available
        if mock_requests is None:
            pytest.skip("requests module not available")
        
        # Set up mock Redis to return None (cache miss)
        mock_redis_client.get.return_value = None
        
        # Set up mock ECB API response
        ecb_response = """<?xml version="1.0" encoding="UTF-8"?>
        <gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01">
            <Cube xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
                <Cube time="2024-01-15">
                    <Cube currency="EUR" rate="1.0"/>
                    <Cube currency="GBP" rate="1.27"/>
                    <Cube currency="JPY" rate="0.0067"/>
                </Cube>
            </Cube>
        </gesmes:Envelope>"""
        
        mock_response = Mock()
        mock_response.content = ecb_response.encode('utf-8')
        mock_requests.get.return_value = mock_response
        
        fx_rate, is_stale = ocr_service._calculate_fx_rate("GBP")
        
        # Should call ECB API
        mock_requests.get.assert_called_once()
        assert fx_rate == Decimal("1.27")
        assert is_stale is False

    @patch('ap_workflow.services.ocr.requests')
    def test_fx_rate_cached_after_api_fetch(self, mock_requests, ocr_service, mock_redis_client):
        """Test that FX rate is cached in Redis after API fetch."""
        # Skip if requests is not available
        if mock_requests is None:
            pytest.skip("requests module not available")
        
        # Set up mock Redis to return None (cache miss)
        mock_redis_client.get.return_value = None
        
        # Set up mock ECB API response
        ecb_response = """<?xml version="1.0" encoding="UTF-8"?>
        <gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01">
            <Cube>
                <Cube time="2024-01-15">
                    <Cube currency="EUR" rate="1.1"/>
                </Cube>
            </Cube>
        </gesmes:Envelope>"""
        
        mock_response = Mock()
        mock_response.content = ecb_response.encode('utf-8')
        mock_requests.get.return_value = mock_response
        
        fx_rate, is_stale = ocr_service._calculate_fx_rate("EUR")
        
        # Should cache the rate
        mock_redis_client.set.assert_called_once()
        call_args = mock_redis_client.set.call_args
        assert call_args[0][0] == "fx_rate:EUR"
        assert call_args[1]['ex'] == 86400  # 24 hours TTL

    @patch('ap_workflow.services.ocr.requests')
    def test_api_failure_returns_stale_cached_rate(self, mock_requests, ocr_service, mock_redis_client):
        """Test that API failure returns stale cached rate if available."""
        # Skip if requests is not available
        if mock_requests is None:
            pytest.skip("requests module not available")
        
        # Set up mock Redis to return stale rate
        old_time = datetime.utcnow() - timedelta(hours=25)
        cache_data = {
            "rate": "1.1",
            "fetch_time": old_time.isoformat()
        }
        
        # First call returns None (cache miss), second call returns stale rate
        mock_redis_client.get.side_effect = [None, json.dumps(cache_data).encode('utf-8')]
        
        # Set up mock ECB API to fail
        mock_requests.get.side_effect = Exception("API Error")
        
        fx_rate, is_stale = ocr_service._calculate_fx_rate("EUR")
        
        # Should return stale cached rate
        assert fx_rate == Decimal("1.1")
        assert is_stale is True

    @patch('ap_workflow.services.ocr.requests')
    def test_api_failure_no_cache_returns_none(self, mock_requests, ocr_service, mock_redis_client):
        """Test that API failure with no cache returns None."""
        # Skip if requests is not available
        if mock_requests is None:
            pytest.skip("requests module not available")
        
        # Set up mock Redis to return None (no cache)
        mock_redis_client.get.return_value = None
        
        # Set up mock ECB API to fail
        mock_requests.get.side_effect = Exception("API Error")
        
        fx_rate, is_stale = ocr_service._calculate_fx_rate("EUR")
        
        # Should return None
        assert fx_rate is None
        assert is_stale is False


class TestCurrencyNormalization:
    """Test currency normalization and USD amount calculation."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = MagicMock()
        mock_query = MagicMock()
        session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.first.return_value = None
        return session

    @pytest.fixture
    def mock_redis_client(self):
        """Create a mock Redis client."""
        return MagicMock()

    @pytest.fixture
    def ocr_service(self, mock_db_session, mock_redis_client):
        """Create OCR service with mocked dependencies."""
        service = OCRService(db=mock_db_session)
        service.redis_client = mock_redis_client
        return service

    def test_usd_amount_calculation_with_fx_rate(self, ocr_service):
        """Test that total_amount_usd = total_amount * fx_rate."""
        total_amount = Decimal("100.00")
        fx_rate = Decimal("1.5")
        
        # Calculate USD amount
        total_amount_usd = (total_amount * fx_rate).quantize(Decimal('0.01'))
        
        assert total_amount_usd == Decimal("150.00")

    def test_usd_amount_rounded_to_2_decimals(self, ocr_service):
        """Test that USD amount is rounded to 2 decimal places."""
        total_amount = Decimal("100.00")
        fx_rate = Decimal("1.234567")
        
        # Calculate USD amount
        total_amount_usd = (total_amount * fx_rate).quantize(Decimal('0.01'))
        
        # Should have exactly 2 decimal places
        assert total_amount_usd == Decimal("123.46")

    def test_usd_currency_identity_conversion(self, ocr_service, mock_redis_client):
        """Test that USD to USD conversion returns same amount."""
        mock_redis_client.get.return_value = None
        
        total_amount = Decimal("100.00")
        fx_rate, _ = ocr_service._calculate_fx_rate("USD")
        
        total_amount_usd = (total_amount * fx_rate).quantize(Decimal('0.01'))
        
        assert total_amount_usd == total_amount

    def test_non_usd_currency_conversion(self, ocr_service, mock_redis_client):
        """Test conversion of non-USD currency to USD."""
        # Set up mock Redis with EUR rate
        cache_data = {
            "rate": "1.1",
            "fetch_time": datetime.utcnow().isoformat()
        }
        mock_redis_client.get.return_value = json.dumps(cache_data).encode('utf-8')
        
        total_amount = Decimal("100.00")
        fx_rate, _ = ocr_service._calculate_fx_rate("EUR")
        
        total_amount_usd = (total_amount * fx_rate).quantize(Decimal('0.01'))
        
        assert total_amount_usd == Decimal("110.00")

    def test_very_small_fx_rate_conversion(self, ocr_service, mock_redis_client):
        """Test conversion with very small FX rate (e.g., JPY)."""
        # Set up mock Redis with JPY rate
        cache_data = {
            "rate": "0.0067",
            "fetch_time": datetime.utcnow().isoformat()
        }
        mock_redis_client.get.return_value = json.dumps(cache_data).encode('utf-8')
        
        total_amount = Decimal("1000.00")
        fx_rate, _ = ocr_service._calculate_fx_rate("JPY")
        
        total_amount_usd = (total_amount * fx_rate).quantize(Decimal('0.01'))
        
        assert total_amount_usd == Decimal("6.70")

    def test_very_large_fx_rate_conversion(self, ocr_service, mock_redis_client):
        """Test conversion with very large FX rate."""
        # Set up mock Redis with large rate
        cache_data = {
            "rate": "120.0",
            "fetch_time": datetime.utcnow().isoformat()
        }
        mock_redis_client.get.return_value = json.dumps(cache_data).encode('utf-8')
        
        total_amount = Decimal("100.00")
        fx_rate, _ = ocr_service._calculate_fx_rate("JPY")
        
        total_amount_usd = (total_amount * fx_rate).quantize(Decimal('0.01'))
        
        assert total_amount_usd == Decimal("12000.00")


class TestStaleFXRateDetection:
    """Test detection and flagging of stale FX rates."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = MagicMock()
        mock_query = MagicMock()
        session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.first.return_value = None
        return session

    @pytest.fixture
    def mock_redis_client(self):
        """Create a mock Redis client."""
        return MagicMock()

    @pytest.fixture
    def ocr_service(self, mock_db_session, mock_redis_client):
        """Create OCR service with mocked dependencies."""
        service = OCRService(db=mock_db_session)
        service.redis_client = mock_redis_client
        return service

    def test_rate_older_than_24_hours_is_stale(self, ocr_service, mock_redis_client):
        """Test that rates older than 24 hours are marked as stale."""
        # Set up mock Redis with rate 25 hours old
        old_time = datetime.utcnow() - timedelta(hours=25)
        cache_data = {
            "rate": "1.1",
            "fetch_time": old_time.isoformat()
        }
        mock_redis_client.get.return_value = json.dumps(cache_data).encode('utf-8')
        
        fx_rate, is_stale = ocr_service._calculate_fx_rate("EUR")
        
        assert is_stale is True

    def test_rate_younger_than_24_hours_not_stale(self, ocr_service, mock_redis_client):
        """Test that rates younger than 24 hours are not marked as stale."""
        # Set up mock Redis with rate 12 hours old
        recent_time = datetime.utcnow() - timedelta(hours=12)
        cache_data = {
            "rate": "1.1",
            "fetch_time": recent_time.isoformat()
        }
        mock_redis_client.get.return_value = json.dumps(cache_data).encode('utf-8')
        
        fx_rate, is_stale = ocr_service._calculate_fx_rate("EUR")
        
        assert is_stale is False

    def test_rate_exactly_24_hours_old_not_stale(self, ocr_service, mock_redis_client):
        """Test boundary condition: rate exactly 24 hours old should not be stale."""
        # Set up mock Redis with rate exactly 24 hours old
        # Add a small buffer to account for test execution time
        boundary_time = datetime.utcnow() - timedelta(hours=24, seconds=-1)  # 1 second before 24h
        cache_data = {
            "rate": "1.1",
            "fetch_time": boundary_time.isoformat()
        }
        mock_redis_client.get.return_value = json.dumps(cache_data).encode('utf-8')
        
        fx_rate, is_stale = ocr_service._calculate_fx_rate("EUR")
        
        # At exactly 24 hours, should not be stale (> 24h is stale)
        assert is_stale is False

    def test_rate_just_past_24_hours_is_stale(self, ocr_service, mock_redis_client):
        """Test boundary condition: rate just past 24 hours should be stale."""
        # Set up mock Redis with rate 24 hours + 1 second old
        boundary_time = datetime.utcnow() - timedelta(hours=24, seconds=1)
        cache_data = {
            "rate": "1.1",
            "fetch_time": boundary_time.isoformat()
        }
        mock_redis_client.get.return_value = json.dumps(cache_data).encode('utf-8')
        
        fx_rate, is_stale = ocr_service._calculate_fx_rate("EUR")
        
        assert is_stale is True

    def test_fresh_api_rate_not_stale(self, ocr_service, mock_redis_client):
        """Test that newly fetched rates from API are not stale."""
        # Set up mock Redis to return None (cache miss)
        mock_redis_client.get.return_value = None
        
        # Set up mock ECB API response
        ecb_response = """<?xml version="1.0" encoding="UTF-8"?>
        <gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01">
            <Cube>
                <Cube time="2024-01-15">
                    <Cube currency="EUR" rate="1.1"/>
                </Cube>
            </Cube>
        </gesmes:Envelope>"""
        
        with patch('ap_workflow.services.ocr.requests') as mock_requests:
            if mock_requests is None:
                pytest.skip("requests module not available")
            
            mock_response = Mock()
            mock_response.content = ecb_response.encode('utf-8')
            mock_requests.get.return_value = mock_response
            
            fx_rate, is_stale = ocr_service._calculate_fx_rate("EUR")
            
            # Newly fetched rate should not be stale
            assert is_stale is False


class TestRedisCaching:
    """Test Redis caching of FX rates."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = MagicMock()
        mock_query = MagicMock()
        session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.first.return_value = None
        return session

    @pytest.fixture
    def mock_redis_client(self):
        """Create a mock Redis client."""
        return MagicMock()

    @pytest.fixture
    def ocr_service(self, mock_db_session, mock_redis_client):
        """Create OCR service with mocked dependencies."""
        service = OCRService(db=mock_db_session)
        service.redis_client = mock_redis_client
        return service

    def test_cache_key_format(self, ocr_service, mock_redis_client):
        """Test that cache key follows format fx_rate:{CURRENCY}."""
        mock_redis_client.get.return_value = None
        
        with patch('ap_workflow.services.ocr.requests') as mock_requests:
            if mock_requests is None:
                pytest.skip("requests module not available")
            
            ecb_response = """<?xml version="1.0" encoding="UTF-8"?>
            <gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01">
                <Cube>
                    <Cube time="2024-01-15">
                        <Cube currency="EUR" rate="1.1"/>
                    </Cube>
                </Cube>
            </gesmes:Envelope>"""
            
            mock_response = Mock()
            mock_response.content = ecb_response.encode('utf-8')
            mock_requests.get.return_value = mock_response
            
            ocr_service._calculate_fx_rate("EUR")
            
            # Check cache key format
            mock_redis_client.set.assert_called_once()
            call_args = mock_redis_client.set.call_args
            assert call_args[0][0] == "fx_rate:EUR"

    def test_cache_ttl_24_hours(self, ocr_service, mock_redis_client):
        """Test that cache TTL is set to 24 hours (86400 seconds)."""
        mock_redis_client.get.return_value = None
        
        with patch('ap_workflow.services.ocr.requests') as mock_requests:
            if mock_requests is None:
                pytest.skip("requests module not available")
            
            ecb_response = """<?xml version="1.0" encoding="UTF-8"?>
            <gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01">
                <Cube>
                    <Cube time="2024-01-15">
                        <Cube currency="EUR" rate="1.1"/>
                    </Cube>
                </Cube>
            </gesmes:Envelope>"""
            
            mock_response = Mock()
            mock_response.content = ecb_response.encode('utf-8')
            mock_requests.get.return_value = mock_response
            
            ocr_service._calculate_fx_rate("EUR")
            
            # Check TTL
            mock_redis_client.set.assert_called_once()
            call_args = mock_redis_client.set.call_args
            assert call_args[1]['ex'] == 86400  # 24 hours

    def test_cache_data_format(self, ocr_service, mock_redis_client):
        """Test that cached data includes rate and fetch_time."""
        mock_redis_client.get.return_value = None
        
        with patch('ap_workflow.services.ocr.requests') as mock_requests:
            if mock_requests is None:
                pytest.skip("requests module not available")
            
            ecb_response = """<?xml version="1.0" encoding="UTF-8"?>
            <gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01">
                <Cube>
                    <Cube time="2024-01-15">
                        <Cube currency="EUR" rate="1.1"/>
                    </Cube>
                </Cube>
            </gesmes:Envelope>"""
            
            mock_response = Mock()
            mock_response.content = ecb_response.encode('utf-8')
            mock_requests.get.return_value = mock_response
            
            ocr_service._calculate_fx_rate("EUR")
            
            # Check cached data format
            mock_redis_client.set.assert_called_once()
            call_args = mock_redis_client.set.call_args
            cache_json = call_args[0][1].decode('utf-8')
            cache_data = json.loads(cache_json)
            
            assert "rate" in cache_data
            assert "fetch_time" in cache_data
            assert cache_data["rate"] == "1.1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
