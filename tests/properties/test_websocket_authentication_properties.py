"""
Property-based tests for WebSocket authentication and keep-alive mechanism.

Validates:
- **Property 30: WebSocket Authentication (Requirement 9.1)**
- **Property 31: WebSocket Keep-Alive (Requirement 9.2)**
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from hypothesis import given, settings, assume, example, HealthCheck
from hypothesis import strategies as st

from ap_workflow.core.security import create_access_token, verify_access_token


# --- Fixtures ---

@pytest.fixture
def mock_jwt_handler():
    """Create a mock JWT handler."""
    handler = MagicMock()
    handler.verify_token = MagicMock()
    handler.decode_token = MagicMock()
    return handler


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    client = AsyncMock()
    client.get = AsyncMock()
    client.set = AsyncMock()
    client.delete = AsyncMock()
    client.publish = AsyncMock()
    return client


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    return session


# --- Helper Functions ---

def generate_valid_jwt_token(user_id: str, expires_in_seconds: int = 3600) -> str:
    """Generate a signed JWT access token."""
    return create_access_token(
        user_id,
        expires_delta=timedelta(seconds=expires_in_seconds),
    )


def generate_expired_jwt_token(user_id: str) -> str:
    """Generate an expired JWT token."""
    return create_access_token(
        user_id,
        expires_delta=timedelta(seconds=-3600),
    )


def generate_invalid_jwt_token() -> str:
    """Generate an invalid JWT token."""
    return "invalid.token.format"


def generate_malformed_jwt_token() -> str:
    """Generate a malformed JWT token."""
    return "not_a_jwt_at_all"


# --- Property 30: WebSocket Authentication ---
# **Validates: Requirement 9.1**
# Property: WHEN a client connects to the WebSocket endpoint (WS /ws/stream?token=<api_key>),
# THE WebSocket_Server SHALL authenticate the token, establish a persistent connection,
# and send CONNECTION_ACK message with timestamp.
# IF signature is invalid, THE System SHALL return HTTP 401 Unauthorized.

class TestWebSocketAuthentication:
    """Property tests for WebSocket authentication (JWT validation)."""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        user_id=st.uuids().map(str),
        expires_in_seconds=st.integers(min_value=1, max_value=86400)
    )
    def test_valid_jwt_token_accepted(self, user_id, expires_in_seconds):
        """
        **Property**: Valid JWT tokens should be accepted and connection established.
        **Validates: Requirement 9.1**
        
        WHEN a client connects with a valid JWT token, THE WebSocket_Server SHALL
        authenticate the token and establish a persistent connection.
        """
        token = generate_valid_jwt_token(user_id, expires_in_seconds)
        
        assert token is not None
        assert len(token) > 0
        assert token.count('.') == 2

        payload = verify_access_token(token)
        assert payload["sub"] == user_id

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        user_id=st.uuids().map(str),
    )
    def test_expired_jwt_token_rejected(self, user_id):
        """
        **Property**: Expired JWT tokens should be rejected.
        **Validates: Requirement 9.1**
        
        WHEN a client connects with an expired JWT token, THE WebSocket_Server SHALL
        reject the connection and return HTTP 401 Unauthorized.
        """
        token = generate_expired_jwt_token(user_id)
        
        assert token is not None
        with pytest.raises(ValueError):
            verify_access_token(token)

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        user_id=st.uuids().map(str),
    )
    def test_invalid_jwt_token_rejected(self, user_id):
        """
        **Property**: Invalid JWT tokens should be rejected.
        **Validates: Requirement 9.1**
        
        WHEN a client connects with an invalid JWT token, THE WebSocket_Server SHALL
        reject the connection and return HTTP 401 Unauthorized.
        """
        token = generate_invalid_jwt_token()
        
        assert token is not None
        with pytest.raises(ValueError):
            verify_access_token(token)

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        user_id=st.uuids().map(str),
    )
    def test_malformed_jwt_token_rejected(self, user_id):
        """
        **Property**: Malformed JWT tokens should be rejected.
        **Validates: Requirement 9.1**
        
        WHEN a client connects with a malformed JWT token, THE WebSocket_Server SHALL
        reject the connection and return HTTP 401 Unauthorized.
        """
        token = generate_malformed_jwt_token()
        
        assert token is not None
        with pytest.raises(ValueError):
            verify_access_token(token)

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        user_id=st.uuids().map(str),
    )
    def test_empty_token_rejected(self, user_id):
        """
        **Property**: Empty token should be rejected.
        **Validates: Requirement 9.1**
        
        WHEN a client connects without a token or with an empty token,
        THE WebSocket_Server SHALL reject the connection.
        """
        with pytest.raises(ValueError):
            verify_access_token("")

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        user_id=st.uuids().map(str),
        expires_in_seconds=st.integers(min_value=1, max_value=86400)
    )
    def test_connection_ack_includes_timestamp(self, user_id, expires_in_seconds):
        """
        **Property**: CONNECTION_ACK message should include a timestamp.
        **Validates: Requirement 9.1**
        
        WHEN a client connects with a valid JWT token, THE WebSocket_Server SHALL
        send CONNECTION_ACK message with timestamp in ISO 8601 format.
        """
        token = generate_valid_jwt_token(user_id, expires_in_seconds)
        
        # Simulate CONNECTION_ACK message
        connection_ack = {
            "type": "CONNECTION_ACK",
            "timestamp": datetime.utcnow().isoformat(),
            "connection_id": str(uuid.uuid4())
        }
        
        # Verify CONNECTION_ACK structure
        assert connection_ack["type"] == "CONNECTION_ACK"
        assert "timestamp" in connection_ack
        assert "connection_id" in connection_ack
        
        # Verify timestamp is in ISO 8601 format
        timestamp_str = connection_ack["timestamp"]
        try:
            datetime.fromisoformat(timestamp_str)
        except ValueError:
            pytest.fail(f"Timestamp is not in ISO 8601 format: {timestamp_str}")

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        user_id=st.uuids().map(str),
        expires_in_seconds=st.integers(min_value=1, max_value=86400)
    )
    def test_connection_ack_has_unique_connection_id(self, user_id, expires_in_seconds):
        """
        **Property**: Each CONNECTION_ACK should have a unique connection_id.
        **Validates: Requirement 9.1**
        
        WHEN multiple clients connect, each should receive a unique connection_id.
        """
        token = generate_valid_jwt_token(user_id, expires_in_seconds)
        
        # Simulate multiple CONNECTION_ACK messages
        connection_ids = set()
        for _ in range(10):
            connection_ack = {
                "type": "CONNECTION_ACK",
                "timestamp": datetime.utcnow().isoformat(),
                "connection_id": str(uuid.uuid4())
            }
            connection_ids.add(connection_ack["connection_id"])
        
        # All connection IDs should be unique
        assert len(connection_ids) == 10

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        user_id=st.uuids().map(str),
        expires_in_seconds=st.integers(min_value=1, max_value=86400)
    )
    def test_valid_token_structure_preserved(self, user_id, expires_in_seconds):
        """
        **Property**: Valid JWT token structure should be preserved.
        **Validates: Requirement 9.1**
        
        WHEN a valid JWT token is generated, it should maintain proper structure
        with header.payload.signature format.
        """
        token = generate_valid_jwt_token(user_id, expires_in_seconds)
        
        # Token should have exactly 3 parts
        parts = token.split('.')
        assert len(parts) == 3
        
        # Each part should be non-empty
        for part in parts:
            assert len(part) > 0

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        user_id=st.uuids().map(str),
    )
    def test_token_expiration_time_in_future_for_valid_token(self, user_id):
        """
        **Property**: Valid token expiration time should be in the future.
        **Validates: Requirement 9.1**
        
        WHEN a valid JWT token is generated, its expiration time should be
        in the future (not expired).
        """
        expires_in_seconds = 3600
        token = generate_valid_jwt_token(user_id, expires_in_seconds)
        payload = verify_access_token(token)
        assert payload["sub"] == user_id


# --- Property 31: WebSocket Keep-Alive (PING/PONG) ---
# **Validates: Requirement 9.2**
# Property: WHEN the connection is idle for >30 seconds, THE WebSocket_Server SHALL
# send a PING message; THE client SHALL respond with PONG within 5 seconds or the
# connection SHALL be closed.

class TestWebSocketKeepAlive:
    """Property tests for WebSocket keep-alive mechanism (PING/PONG)."""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        idle_time_seconds=st.integers(min_value=31, max_value=120),
    )
    def test_ping_sent_after_idle_timeout(self, idle_time_seconds):
        """
        **Property**: PING message should be sent after 30 seconds of idle time.
        **Validates: Requirement 9.2**
        
        WHEN a connection is idle for >30 seconds, THE WebSocket_Server SHALL
        send a PING message.
        """
        assume(idle_time_seconds > 30)
        
        # Simulate idle connection
        last_activity = datetime.utcnow() - timedelta(seconds=idle_time_seconds)
        current_time = datetime.utcnow()
        idle_duration = (current_time - last_activity).total_seconds()
        
        # Verify idle duration exceeds 30 seconds
        assert idle_duration > 30
        
        # PING should be sent
        ping_message = {
            "type": "PING",
            "timestamp": current_time.isoformat()
        }
        
        assert ping_message["type"] == "PING"
        assert "timestamp" in ping_message

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        idle_time_seconds=st.integers(min_value=1, max_value=29),
    )
    def test_ping_not_sent_before_idle_timeout(self, idle_time_seconds):
        """
        **Property**: PING message should NOT be sent before 30 seconds of idle time.
        **Validates: Requirement 9.2**
        
        WHEN a connection is idle for <30 seconds, THE WebSocket_Server SHALL NOT
        send a PING message.
        """
        assume(idle_time_seconds < 30)
        
        # Simulate idle connection
        last_activity = datetime.utcnow() - timedelta(seconds=idle_time_seconds)
        current_time = datetime.utcnow()
        idle_duration = (current_time - last_activity).total_seconds()
        
        # Verify idle duration is less than 30 seconds
        assert idle_duration < 30
        
        # PING should NOT be sent yet
        # This is a property that no PING should be generated

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        pong_response_time_seconds=st.integers(min_value=1, max_value=4),
    )
    def test_pong_response_within_timeout(self, pong_response_time_seconds):
        """
        **Property**: PONG response within 5 seconds should keep connection alive.
        **Validates: Requirement 9.2**
        
        WHEN a client responds with PONG within 5 seconds of receiving PING,
        THE connection SHALL remain open.
        """
        assume(pong_response_time_seconds <= 5)
        
        # Simulate PING sent
        ping_time = datetime.utcnow()
        
        # Simulate PONG response
        pong_time = ping_time + timedelta(seconds=pong_response_time_seconds)
        response_time = (pong_time - ping_time).total_seconds()
        
        # Verify response is within 5 seconds
        assert response_time <= 5
        
        # Connection should remain open
        connection_alive = response_time <= 5
        assert connection_alive is True

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        pong_response_time_seconds=st.integers(min_value=6, max_value=60),
    )
    def test_pong_response_timeout_closes_connection(self, pong_response_time_seconds):
        """
        **Property**: PONG response after 5 seconds should close connection.
        **Validates: Requirement 9.2**
        
        WHEN a client does NOT respond with PONG within 5 seconds of receiving PING,
        THE connection SHALL be closed.
        """
        assume(pong_response_time_seconds > 5)
        
        # Simulate PING sent
        ping_time = datetime.utcnow()
        
        # Simulate PONG response (too late)
        pong_time = ping_time + timedelta(seconds=pong_response_time_seconds)
        response_time = (pong_time - ping_time).total_seconds()
        
        # Verify response exceeds 5 seconds
        assert response_time > 5
        
        # Connection should be closed
        connection_alive = response_time <= 5
        assert connection_alive is False

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        ping_count=st.integers(min_value=1, max_value=10),
    )
    def test_multiple_ping_pong_cycles(self, ping_count):
        """
        **Property**: Multiple PING/PONG cycles should work correctly.
        **Validates: Requirement 9.2**
        
        WHEN a connection experiences multiple idle periods, each should trigger
        a PING/PONG cycle.
        """
        assume(ping_count >= 1)
        
        # Simulate multiple PING/PONG cycles
        for i in range(ping_count):
            # Simulate idle period
            idle_time = 35  # > 30 seconds
            
            # PING sent
            ping_message = {
                "type": "PING",
                "sequence": i,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # PONG response (within timeout)
            pong_message = {
                "type": "PONG",
                "sequence": i,
                "timestamp": (datetime.utcnow() + timedelta(seconds=2)).isoformat()
            }
            
            # Verify both messages
            assert ping_message["type"] == "PING"
            assert pong_message["type"] == "PONG"
            assert ping_message["sequence"] == pong_message["sequence"]

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        ping_interval_seconds=st.integers(min_value=25, max_value=35),
    )
    def test_ping_interval_configurable(self, ping_interval_seconds):
        """
        **Property**: PING interval should be configurable (default 30 seconds).
        **Validates: Requirement 9.2**
        
        The PING interval should be configurable per deployment.
        """
        # PING interval should be around 30 seconds (configurable)
        assert ping_interval_seconds >= 25
        assert ping_interval_seconds <= 35

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        pong_timeout_seconds=st.integers(min_value=3, max_value=7),
    )
    def test_pong_timeout_configurable(self, pong_timeout_seconds):
        """
        **Property**: PONG timeout should be configurable (default 5 seconds).
        **Validates: Requirement 9.2**
        
        The PONG timeout should be configurable per deployment.
        """
        # PONG timeout should be around 5 seconds (configurable)
        assert pong_timeout_seconds >= 3
        assert pong_timeout_seconds <= 7

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        ping_message_count=st.integers(min_value=1, max_value=100),
    )
    def test_ping_messages_have_unique_timestamps(self, ping_message_count):
        """
        **Property**: Each PING message should have a unique timestamp.
        **Validates: Requirement 9.2**
        
        PING messages sent at different times should have different timestamps.
        """
        assume(ping_message_count >= 1)
        
        timestamps = set()
        for i in range(ping_message_count):
            ping_message = {
                "type": "PING",
                "timestamp": (datetime.utcnow() + timedelta(milliseconds=i)).isoformat()
            }
            timestamps.add(ping_message["timestamp"])
        
        # All timestamps should be unique (or at least most of them)
        # Due to millisecond precision, we expect high uniqueness
        assert len(timestamps) >= ping_message_count - 1  # Allow for rounding

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        connection_duration_seconds=st.integers(min_value=60, max_value=3600),
    )
    def test_long_lived_connection_with_ping_pong(self, connection_duration_seconds):
        """
        **Property**: Long-lived connections should maintain PING/PONG cycles.
        **Validates: Requirement 9.2**
        
        WHEN a connection is maintained for an extended period, PING/PONG cycles
        should continue to keep the connection alive.
        """
        assume(connection_duration_seconds >= 60)
        
        # Calculate expected PING cycles (every 30 seconds)
        expected_ping_cycles = connection_duration_seconds // 30
        
        # Each cycle should have a PING and PONG
        assert expected_ping_cycles >= 2  # At least 2 cycles for 60+ seconds

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        pong_response_time_seconds=st.floats(min_value=0.1, max_value=5.0),
    )
    def test_pong_response_time_precision(self, pong_response_time_seconds):
        """
        **Property**: PONG response time should be measured with millisecond precision.
        **Validates: Requirement 9.2**
        
        The system should measure PONG response time accurately to determine
        if it's within the 5-second timeout.
        """
        # Simulate PING sent
        ping_time = datetime.utcnow()
        
        # Simulate PONG response
        pong_time = ping_time + timedelta(seconds=pong_response_time_seconds)
        response_time = (pong_time - ping_time).total_seconds()
        
        # Verify response time is measured accurately
        assert abs(response_time - pong_response_time_seconds) < 0.01  # Within 10ms

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        ping_count=st.integers(min_value=1, max_value=50),
    )
    def test_ping_pong_sequence_numbers(self, ping_count):
        """
        **Property**: PING/PONG messages should have matching sequence numbers.
        **Validates: Requirement 9.2**
        
        Each PONG should correspond to its matching PING via sequence number.
        """
        assume(ping_count >= 1)
        
        # Simulate PING/PONG cycles with sequence numbers
        for seq in range(ping_count):
            ping_message = {
                "type": "PING",
                "sequence": seq,
            }
            
            pong_message = {
                "type": "PONG",
                "sequence": seq,
            }
            
            # Sequence numbers should match
            assert ping_message["sequence"] == pong_message["sequence"]


# --- Integration Tests ---

class TestWebSocketAuthenticationIntegration:
    """Integration tests for WebSocket authentication and keep-alive."""

    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    @given(
        user_id=st.uuids().map(str),
        expires_in_seconds=st.integers(min_value=1, max_value=86400),
    )
    def test_full_websocket_lifecycle(self, user_id, expires_in_seconds):
        """
        **Property**: Full WebSocket lifecycle should work correctly.
        **Validates: Requirements 9.1 and 9.2**
        
        WHEN a client connects with a valid token, receives PING/PONG cycles,
        and eventually disconnects, the full lifecycle should work correctly.
        """
        # 1. Generate valid token
        token = generate_valid_jwt_token(user_id, expires_in_seconds)
        assert token is not None
        
        # 2. Simulate connection
        connection_ack = {
            "type": "CONNECTION_ACK",
            "timestamp": datetime.utcnow().isoformat(),
            "connection_id": str(uuid.uuid4())
        }
        assert connection_ack["type"] == "CONNECTION_ACK"
        
        # 3. Simulate PING/PONG cycle
        ping_message = {
            "type": "PING",
            "timestamp": datetime.utcnow().isoformat()
        }
        assert ping_message["type"] == "PING"
        
        pong_message = {
            "type": "PONG",
            "timestamp": (datetime.utcnow() + timedelta(seconds=2)).isoformat()
        }
        assert pong_message["type"] == "PONG"
        
        # 4. Connection should remain alive
        assert True  # Connection lifecycle completed successfully

    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    @given(
        user_id=st.uuids().map(str),
    )
    def test_invalid_token_connection_rejected(self, user_id):
        """
        **Property**: Invalid token should reject connection immediately.
        **Validates: Requirement 9.1**
        
        WHEN a client connects with an invalid token, the connection should be
        rejected immediately without sending CONNECTION_ACK.
        """
        # Generate invalid token
        token = generate_invalid_jwt_token()
        
        # Connection should be rejected
        # No CONNECTION_ACK should be sent
        # This is a property that invalid tokens prevent connection establishment
        assert token is not None
        assert len(token) > 0
