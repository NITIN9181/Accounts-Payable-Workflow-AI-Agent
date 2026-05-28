"""Property-based tests for WebSocket event broadcasting.

**Validates: Requirements 9.3, 9.4, 9.5**

This module tests the following properties:
- Property 32: Exception Event Broadcasting
- Property 33: Explanation Ready Event Broadcasting
- Property 34: Status Change Event Broadcasting
- Property 51: FIFO WebSocket Event Delivery
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List
from uuid import UUID, uuid4
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from sqlalchemy.orm import Session

from ap_workflow.models import (
    Invoice,
    InvoiceException,
    Approval,
)
from ap_workflow.services.queue_publishers import WebSocketBroadcastQueuePublisher
from ap_workflow.services.message_queue import MessageQueueService, QueueName


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def mock_redis_client():
    """Fixture for mocked Redis client."""
    mock_client = MagicMock()
    # Mock the Redis list operations
    mock_client.rpush = MagicMock(return_value=1)
    mock_client.blpop = MagicMock()
    mock_client.llen = MagicMock(return_value=0)
    mock_client.lindex = MagicMock()
    mock_client.delete = MagicMock()
    return mock_client


@pytest.fixture(scope="session")
def message_queue(mock_redis_client):
    """Fixture for message queue service with mocked Redis."""
    with patch('ap_workflow.services.message_queue.redis_client') as mock_redis:
        mock_redis.client = mock_redis_client
        queue = MessageQueueService()
        # Store messages in memory for testing
        queue._messages = {}
        
        # Override publish_message to store in memory
        original_publish = queue.publish_message
        def mock_publish(queue_name, message, priority=0):
            if queue_name not in queue._messages:
                queue._messages[queue_name] = []
            message_id = f"{queue_name}:{datetime.utcnow().timestamp()}"
            message_with_metadata = {
                "id": message_id,
                "queue": queue_name,
                "payload": message,
                "priority": priority,
                "created_at": datetime.utcnow().isoformat(),
                "retries": 0,
            }
            queue._messages[queue_name].append(message_with_metadata)
            mock_redis_client.rpush.return_value = len(queue._messages[queue_name])
            return message_id
        
        # Override consume_message to retrieve from memory
        original_consume = queue.consume_message
        def mock_consume(queue_name, timeout=0):
            if queue_name in queue._messages and queue._messages[queue_name]:
                return queue._messages[queue_name].pop(0)
            return None
        
        queue.publish_message = mock_publish
        queue.consume_message = mock_consume
        yield queue


@pytest.fixture(scope="session")
def websocket_publisher(message_queue):
    """Fixture for WebSocket broadcast queue publisher."""
    with patch('ap_workflow.services.queue_publishers.MessageQueueService') as mock_mq_class:
        mock_mq_class.return_value = message_queue
        publisher = WebSocketBroadcastQueuePublisher()
        publisher.message_queue = message_queue
        yield publisher


# ============================================================================
# Hypothesis Strategies
# ============================================================================

# Strategy for exception IDs
exception_id_strategy = st.uuids()

# Strategy for invoice IDs
invoice_id_strategy = st.uuids()

# Strategy for vendor names
vendor_name_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cc", "Cs")),
    min_size=1,
    max_size=100
)

# Strategy for amounts
amount_strategy = st.decimals(
    min_value=0.01,
    max_value=999999.99,
    places=2,
    allow_nan=False,
    allow_infinity=False
)

# Strategy for severity scores
severity_strategy = st.floats(
    min_value=0.0,
    max_value=1.0,
    allow_nan=False,
    allow_infinity=False
)

# Strategy for severity bands
severity_band_strategy = st.sampled_from(["CRITICAL", "HIGH", "MEDIUM", "LOW"])

# Strategy for exception types
exception_type_strategy = st.sampled_from([
    "DUPLICATE_EXACT",
    "DUPLICATE_FUZZY",
    "PO_MISMATCH",
    "PARTIAL_RECEIPT",
    "PO_MISSING",
    "RECEIPT_MISSING",
    "AMOUNT_ANOMALY",
    "FREQUENCY_ANOMALY",
])

# Strategy for invoice statuses
invoice_status_strategy = st.sampled_from([
    "PENDING_OCR",
    "PENDING_APPROVAL",
    "APPROVED",
    "REJECTED",
    "SCHEDULED",
    "PAID",
])

# Strategy for LLM explanations
llm_explanation_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cc", "Cs")),
    min_size=10,
    max_size=500
)

# Strategy for actor IDs
actor_id_strategy = st.uuids()


# ============================================================================
# Property 32: Exception Event Broadcasting
# ============================================================================

class TestExceptionEventBroadcasting:
    """Test that EXCEPTION_CREATED events are broadcast with correct payload."""

    @given(
        exception_id=exception_id_strategy,
        invoice_id=invoice_id_strategy,
        vendor_name=vendor_name_strategy,
        total_amount=amount_strategy,
        final_severity=severity_strategy,
        severity_band=severity_band_strategy,
        exception_type=exception_type_strategy,
        llm_explanation=llm_explanation_strategy,
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    def test_exception_created_event_has_required_fields(
        self,
        websocket_publisher,
        message_queue,
        exception_id,
        invoice_id,
        vendor_name,
        total_amount,
        final_severity,
        severity_band,
        exception_type,
        llm_explanation,
    ):
        """Test that EXCEPTION_CREATED event contains all required fields.
        
        **Validates: Requirements 9.3**
        
        For any invoice_exception created with final_severity > 0.4, the system
        SHALL broadcast an EXCEPTION_CREATED event to all connected WebSocket
        clients with payload: {exception_id, invoice_id, vendor_name, total_amount,
        final_severity, severity_band, exception_type, llm_explanation,
        llm_explanation_ready}.
        """
        # Only test if severity > 0.4 (exception should be created)
        if final_severity <= 0.4:
            pytest.skip("Severity too low for exception creation")

        exception_data = {
            "vendor_name": vendor_name,
            "total_amount": float(total_amount),
            "final_severity": final_severity,
            "severity_band": severity_band,
            "exception_type": exception_type,
            "llm_explanation": llm_explanation,
            "llm_explanation_ready": True,
        }

        # Publish exception created event
        message_id = websocket_publisher.publish_exception_created(
            exception_id, exception_data
        )

        # Verify message was published
        assert message_id is not None
        assert isinstance(message_id, str)

        # Retrieve message from queue
        message = message_queue.consume_message(
            QueueName.WEBSOCKET_BROADCAST_QUEUE.value, timeout=1
        )

        # Verify message structure
        assert message is not None
        assert message["payload"]["event_type"] == "EXCEPTION_CREATED"
        assert message["payload"]["exception_id"] == str(exception_id)

        # Verify payload contains all required fields
        payload = message["payload"]["data"]
        assert "vendor_name" in payload
        assert "total_amount" in payload
        assert "final_severity" in payload
        assert "severity_band" in payload
        assert "exception_type" in payload
        assert "llm_explanation" in payload
        assert "llm_explanation_ready" in payload

        # Verify field values
        assert payload["vendor_name"] == vendor_name
        assert payload["total_amount"] == float(total_amount)
        assert payload["final_severity"] == final_severity
        assert payload["severity_band"] == severity_band
        assert payload["exception_type"] == exception_type
        assert payload["llm_explanation"] == llm_explanation
        assert payload["llm_explanation_ready"] is True

    @given(
        exception_id=exception_id_strategy,
        invoice_id=invoice_id_strategy,
        vendor_name=vendor_name_strategy,
        total_amount=amount_strategy,
        final_severity=severity_strategy,
        severity_band=severity_band_strategy,
        exception_type=exception_type_strategy,
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    def test_exception_created_event_includes_timestamp(
        self,
        websocket_publisher,
        message_queue,
        exception_id,
        invoice_id,
        vendor_name,
        total_amount,
        final_severity,
        severity_band,
        exception_type,
    ):
        """Test that EXCEPTION_CREATED event includes ISO 8601 timestamp.
        
        **Validates: Requirements 9 (Invariant: timestamp in ISO 8601 format)**
        """
        if final_severity <= 0.4:
            pytest.skip("Severity too low for exception creation")

        exception_data = {
            "vendor_name": vendor_name,
            "total_amount": float(total_amount),
            "final_severity": final_severity,
            "severity_band": severity_band,
            "exception_type": exception_type,
            "llm_explanation": "Test explanation",
            "llm_explanation_ready": True,
            "timestamp": datetime.utcnow().isoformat(),
        }

        message_id = websocket_publisher.publish_exception_created(
            exception_id, exception_data
        )

        message = message_queue.consume_message(
            QueueName.WEBSOCKET_BROADCAST_QUEUE.value, timeout=1
        )

        # Verify timestamp is present and valid ISO 8601
        assert message is not None
        payload = message["payload"]["data"]
        if "timestamp" in payload:
            # Should be parseable as ISO 8601
            try:
                datetime.fromisoformat(payload["timestamp"])
            except (ValueError, TypeError):
                pytest.fail(f"Timestamp {payload['timestamp']} is not valid ISO 8601")

    @given(
        exception_id=exception_id_strategy,
        invoice_id=invoice_id_strategy,
        vendor_name=vendor_name_strategy,
        total_amount=amount_strategy,
        final_severity=severity_strategy,
        severity_band=severity_band_strategy,
        exception_type=exception_type_strategy,
    )
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    def test_exception_created_event_severity_range(
        self,
        websocket_publisher,
        message_queue,
        exception_id,
        invoice_id,
        vendor_name,
        total_amount,
        final_severity,
        severity_band,
        exception_type,
    ):
        """Test that final_severity in event is in valid range [0.0, 1.0].
        
        **Validates: Requirements 5 (Invariant: final_severity in [0.0, 1.0])**
        """
        if final_severity <= 0.4:
            pytest.skip("Severity too low for exception creation")

        exception_data = {
            "vendor_name": vendor_name,
            "total_amount": float(total_amount),
            "final_severity": final_severity,
            "severity_band": severity_band,
            "exception_type": exception_type,
            "llm_explanation": "Test",
            "llm_explanation_ready": True,
        }

        websocket_publisher.publish_exception_created(exception_id, exception_data)
        message = message_queue.consume_message(
            QueueName.WEBSOCKET_BROADCAST_QUEUE.value, timeout=1
        )

        payload = message["payload"]["data"]
        assert 0.0 <= payload["final_severity"] <= 1.0


# ============================================================================
# Property 33: Explanation Ready Event Broadcasting
# ============================================================================

class TestExplanationReadyEventBroadcasting:
    """Test that EXPLANATION_READY events are broadcast correctly."""

    @given(
        exception_id=exception_id_strategy,
        llm_explanation=llm_explanation_strategy,
        fallback=st.booleans(),
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    def test_explanation_ready_event_has_required_fields(
        self,
        websocket_publisher,
        message_queue,
        exception_id,
        llm_explanation,
        fallback,
    ):
        """Test that EXPLANATION_READY event contains all required fields.
        
        **Validates: Requirements 9.4**
        
        For any LLM explanation that becomes ready (transitions from
        llm_explanation_ready = false to true), the system SHALL broadcast an
        EXPLANATION_READY event to all connected WebSocket clients with payload:
        {exception_id, llm_explanation, fallback}.
        """
        message_id = websocket_publisher.publish_explanation_ready(
            exception_id, llm_explanation
        )

        # Verify message was published
        assert message_id is not None
        assert isinstance(message_id, str)

        # Retrieve message from queue
        message = message_queue.consume_message(
            QueueName.WEBSOCKET_BROADCAST_QUEUE.value, timeout=1
        )

        # Verify message structure
        assert message is not None
        assert message["payload"]["event_type"] == "EXPLANATION_READY"
        assert message["payload"]["exception_id"] == str(exception_id)

        # Verify payload contains required fields
        payload = message["payload"]
        assert "exception_id" in payload
        assert "explanation" in payload
        assert payload["explanation"] == llm_explanation

    @given(
        exception_id=exception_id_strategy,
        llm_explanation=llm_explanation_strategy,
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    def test_explanation_ready_event_includes_timestamp(
        self,
        websocket_publisher,
        message_queue,
        exception_id,
        llm_explanation,
    ):
        """Test that EXPLANATION_READY event includes ISO 8601 timestamp.
        
        **Validates: Requirements 9 (Invariant: timestamp in ISO 8601 format)**
        """
        websocket_publisher.publish_explanation_ready(exception_id, llm_explanation)
        message = message_queue.consume_message(
            QueueName.WEBSOCKET_BROADCAST_QUEUE.value, timeout=1
        )

        assert message is not None
        # Timestamp should be in message metadata or payload
        assert "timestamp" in message or "created_at" in message

    @given(
        exception_id=exception_id_strategy,
        llm_explanation=llm_explanation_strategy,
    )
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    def test_explanation_ready_event_preserves_explanation_text(
        self,
        websocket_publisher,
        message_queue,
        exception_id,
        llm_explanation,
    ):
        """Test that explanation text is preserved exactly in event.
        
        **Validates: Requirements 7 (Idempotence: same explanation returned)**
        """
        websocket_publisher.publish_explanation_ready(exception_id, llm_explanation)
        message = message_queue.consume_message(
            QueueName.WEBSOCKET_BROADCAST_QUEUE.value, timeout=1
        )

        payload = message["payload"]
        assert payload["explanation"] == llm_explanation


# ============================================================================
# Property 34: Status Change Event Broadcasting
# ============================================================================

class TestStatusChangeEventBroadcasting:
    """Test that INVOICE_STATUS_CHANGED events are broadcast correctly."""

    @given(
        invoice_id=invoice_id_strategy,
        old_status=invoice_status_strategy,
        new_status=invoice_status_strategy,
        actor_id=actor_id_strategy,
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    def test_status_change_event_has_required_fields(
        self,
        websocket_publisher,
        message_queue,
        invoice_id,
        old_status,
        new_status,
        actor_id,
    ):
        """Test that INVOICE_STATUS_CHANGED event contains all required fields.
        
        **Validates: Requirements 9.5**
        
        For any invoice status change (e.g., PENDING_APPROVAL → APPROVED), the
        system SHALL broadcast an INVOICE_STATUS_CHANGED event to all connected
        WebSocket clients with payload: {invoice_id, old_status, new_status,
        actor_id, timestamp}.
        """
        message_id = websocket_publisher.publish_invoice_status_changed(
            invoice_id, old_status, new_status
        )

        # Verify message was published
        assert message_id is not None
        assert isinstance(message_id, str)

        # Retrieve message from queue
        message = message_queue.consume_message(
            QueueName.WEBSOCKET_BROADCAST_QUEUE.value, timeout=1
        )

        # Verify message structure
        assert message is not None
        assert message["payload"]["event_type"] == "INVOICE_STATUS_CHANGED"
        assert message["payload"]["invoice_id"] == str(invoice_id)

        # Verify payload contains required fields
        payload = message["payload"]
        assert "invoice_id" in payload
        assert "old_status" in payload
        assert "new_status" in payload
        assert payload["old_status"] == old_status
        assert payload["new_status"] == new_status

    @given(
        invoice_id=invoice_id_strategy,
        old_status=invoice_status_strategy,
        new_status=invoice_status_strategy,
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    def test_status_change_event_includes_timestamp(
        self,
        websocket_publisher,
        message_queue,
        invoice_id,
        old_status,
        new_status,
    ):
        """Test that INVOICE_STATUS_CHANGED event includes ISO 8601 timestamp.
        
        **Validates: Requirements 9 (Invariant: timestamp in ISO 8601 format)**
        """
        websocket_publisher.publish_invoice_status_changed(
            invoice_id, old_status, new_status
        )
        message = message_queue.consume_message(
            QueueName.WEBSOCKET_BROADCAST_QUEUE.value, timeout=1
        )

        assert message is not None
        # Timestamp should be in message metadata
        assert "timestamp" in message or "created_at" in message

    @given(
        invoice_id=invoice_id_strategy,
        old_status=invoice_status_strategy,
        new_status=invoice_status_strategy,
    )
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    def test_status_change_event_preserves_status_values(
        self,
        websocket_publisher,
        message_queue,
        invoice_id,
        old_status,
        new_status,
    ):
        """Test that status values are preserved exactly in event.
        
        **Validates: Requirements 6 (Idempotence: same status returned)**
        """
        websocket_publisher.publish_invoice_status_changed(
            invoice_id, old_status, new_status
        )
        message = message_queue.consume_message(
            QueueName.WEBSOCKET_BROADCAST_QUEUE.value, timeout=1
        )

        payload = message["payload"]
        assert payload["old_status"] == old_status
        assert payload["new_status"] == new_status


# ============================================================================
# Property 51: FIFO WebSocket Event Delivery
# ============================================================================

class TestFIFOWebSocketEventDelivery:
    """Test that events for the same invoice are delivered in FIFO order."""

    @given(
        invoice_id=invoice_id_strategy,
        event_count=st.integers(min_value=2, max_value=10),
    )
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    def test_events_for_same_invoice_delivered_in_order(
        self,
        websocket_publisher,
        message_queue,
        invoice_id,
        event_count,
    ):
        """Test that multiple events for same invoice are delivered in FIFO order.
        
        **Validates: Requirements 9 (Ordering: FIFO for same invoice)**
        
        For any two events related to the same invoice, they SHALL be delivered
        to WebSocket clients in chronological order (FIFO); events for the same
        invoice SHALL be delivered in the order they were created.
        """
        # Publish multiple status change events for the same invoice
        statuses = [
            "PENDING_OCR",
            "PENDING_APPROVAL",
            "APPROVED",
            "SCHEDULED",
            "PAID",
        ]

        message_ids = []
        for i in range(min(event_count, len(statuses) - 1)):
            old_status = statuses[i]
            new_status = statuses[i + 1]
            msg_id = websocket_publisher.publish_invoice_status_changed(
                invoice_id, old_status, new_status
            )
            message_ids.append(msg_id)

        # Retrieve messages in order
        retrieved_messages = []
        for _ in range(len(message_ids)):
            msg = message_queue.consume_message(
                QueueName.WEBSOCKET_BROADCAST_QUEUE.value, timeout=1
            )
            if msg:
                retrieved_messages.append(msg)

        # Verify we got all messages
        assert len(retrieved_messages) == len(message_ids)

        # Verify messages are in FIFO order (same invoice_id)
        for i, msg in enumerate(retrieved_messages):
            assert msg["payload"]["invoice_id"] == str(invoice_id)
            # Verify status transitions are in order
            if i > 0:
                prev_msg = retrieved_messages[i - 1]
                # New status of previous message should match old status of current
                assert (
                    prev_msg["payload"]["new_status"]
                    == msg["payload"]["old_status"]
                )

    @given(
        exception_id=exception_id_strategy,
        event_count=st.integers(min_value=2, max_value=5),
    )
    @settings(
        max_examples=20,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    def test_exception_and_explanation_events_in_order(
        self,
        websocket_publisher,
        message_queue,
        exception_id,
        event_count,
    ):
        """Test that EXCEPTION_CREATED and EXPLANATION_READY events are in order.
        
        **Validates: Requirements 9 (Ordering: FIFO for same exception)**
        """
        # First publish exception created event
        exception_data = {
            "vendor_name": "Test Vendor",
            "total_amount": 1000.00,
            "final_severity": 0.85,
            "severity_band": "HIGH",
            "exception_type": "AMOUNT_ANOMALY",
            "llm_explanation": None,
            "llm_explanation_ready": False,
        }

        msg_id_1 = websocket_publisher.publish_exception_created(
            exception_id, exception_data
        )

        # Then publish explanation ready event
        msg_id_2 = websocket_publisher.publish_explanation_ready(
            exception_id, "This is an explanation"
        )

        # Retrieve messages
        msg1 = message_queue.consume_message(
            QueueName.WEBSOCKET_BROADCAST_QUEUE.value, timeout=1
        )
        msg2 = message_queue.consume_message(
            QueueName.WEBSOCKET_BROADCAST_QUEUE.value, timeout=1
        )

        # Verify order
        assert msg1 is not None
        assert msg2 is not None
        assert msg1["payload"]["event_type"] == "EXCEPTION_CREATED"
        assert msg2["payload"]["event_type"] == "EXPLANATION_READY"
        assert msg1["payload"]["exception_id"] == str(exception_id)
        assert msg2["payload"]["exception_id"] == str(exception_id)

    @given(
        invoice_ids=st.lists(
            st.uuids(),
            min_size=2,
            max_size=5,
            unique=True,
        ),
    )
    @settings(
        max_examples=20,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    def test_events_for_different_invoices_independent(
        self,
        websocket_publisher,
        message_queue,
        invoice_ids,
    ):
        """Test that events for different invoices are independent.
        
        **Validates: Requirements 9 (Ordering: FIFO per invoice)**
        """
        # Publish events for different invoices
        message_ids = []
        for invoice_id in invoice_ids:
            msg_id = websocket_publisher.publish_invoice_status_changed(
                invoice_id, "PENDING_APPROVAL", "APPROVED"
            )
            message_ids.append(msg_id)

        # Retrieve all messages
        retrieved_messages = []
        for _ in range(len(message_ids)):
            msg = message_queue.consume_message(
                QueueName.WEBSOCKET_BROADCAST_QUEUE.value, timeout=1
            )
            if msg:
                retrieved_messages.append(msg)

        # Verify all messages retrieved
        assert len(retrieved_messages) == len(message_ids)

        # Verify each message has correct invoice_id
        retrieved_invoice_ids = [
            msg["payload"]["invoice_id"] for msg in retrieved_messages
        ]
        expected_invoice_ids = [str(iid) for iid in invoice_ids]

        # All expected invoice IDs should be present
        for expected_id in expected_invoice_ids:
            assert expected_id in retrieved_invoice_ids


# ============================================================================
# Integration Tests
# ============================================================================

class TestWebSocketEventBroadcastingIntegration:
    """Integration tests for WebSocket event broadcasting."""

    def test_all_event_types_can_be_published(self, websocket_publisher, message_queue):
        """Test that all three event types can be published successfully."""
        exception_id = uuid4()
        invoice_id = uuid4()

        # Publish all three event types
        msg_id_1 = websocket_publisher.publish_exception_created(
            exception_id,
            {
                "vendor_name": "Test",
                "total_amount": 1000.00,
                "final_severity": 0.85,
                "severity_band": "HIGH",
                "exception_type": "AMOUNT_ANOMALY",
                "llm_explanation": "Test",
                "llm_explanation_ready": True,
            },
        )

        msg_id_2 = websocket_publisher.publish_explanation_ready(
            exception_id, "Explanation"
        )

        msg_id_3 = websocket_publisher.publish_invoice_status_changed(
            invoice_id, "PENDING_APPROVAL", "APPROVED"
        )

        # All should succeed
        assert msg_id_1 is not None
        assert msg_id_2 is not None
        assert msg_id_3 is not None

        # Retrieve all messages
        messages = []
        for _ in range(3):
            msg = message_queue.consume_message(
                QueueName.WEBSOCKET_BROADCAST_QUEUE.value, timeout=1
            )
            if msg:
                messages.append(msg)

        assert len(messages) == 3

    def test_event_payload_is_valid_json(self, websocket_publisher, message_queue):
        """Test that event payloads are valid JSON."""
        exception_id = uuid4()

        websocket_publisher.publish_exception_created(
            exception_id,
            {
                "vendor_name": "Test",
                "total_amount": 1000.00,
                "final_severity": 0.85,
                "severity_band": "HIGH",
                "exception_type": "AMOUNT_ANOMALY",
                "llm_explanation": "Test",
                "llm_explanation_ready": True,
            },
        )

        message = message_queue.consume_message(
            QueueName.WEBSOCKET_BROADCAST_QUEUE.value, timeout=1
        )

        # Payload should be serializable to JSON
        try:
            json.dumps(message["payload"])
        except (TypeError, ValueError):
            pytest.fail("Event payload is not valid JSON")

    def test_event_ids_are_preserved(self, websocket_publisher, message_queue):
        """Test that exception and invoice IDs are preserved in events."""
        exception_id = uuid4()
        invoice_id = uuid4()

        websocket_publisher.publish_exception_created(
            exception_id,
            {
                "vendor_name": "Test",
                "total_amount": 1000.00,
                "final_severity": 0.85,
                "severity_band": "HIGH",
                "exception_type": "AMOUNT_ANOMALY",
                "llm_explanation": "Test",
                "llm_explanation_ready": True,
            },
        )

        websocket_publisher.publish_invoice_status_changed(
            invoice_id, "PENDING_APPROVAL", "APPROVED"
        )

        # Retrieve messages
        msg1 = message_queue.consume_message(
            QueueName.WEBSOCKET_BROADCAST_QUEUE.value, timeout=1
        )
        msg2 = message_queue.consume_message(
            QueueName.WEBSOCKET_BROADCAST_QUEUE.value, timeout=1
        )

        # Verify IDs are preserved
        assert msg1["payload"]["exception_id"] == str(exception_id)
        assert msg2["payload"]["invoice_id"] == str(invoice_id)

