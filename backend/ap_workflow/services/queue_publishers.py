"""Message queue publishers for AP Workflow Agent."""

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from ap_workflow.services.message_queue import MessageQueueService, QueueName

logger = logging.getLogger(__name__)


class QueuePublisher:
    """Base class for queue publishers."""

    def __init__(self):
        """Initialize queue publisher."""
        self.message_queue = MessageQueueService()


class InvoiceQueuePublisher(QueuePublisher):
    """Publisher for invoice queue (from Ingestion Service)."""

    def publish_invoice(self, invoice_id: UUID, invoice_data: Dict[str, Any]) -> str:
        """Publish invoice to OCR queue.

        Args:
            invoice_id: ID of the invoice
            invoice_data: Invoice data

        Returns:
            Message ID
        """
        message = {
            "invoice_id": str(invoice_id),
            "data": invoice_data,
        }
        return self.message_queue.publish_message(QueueName.INVOICE_QUEUE.value, message)


class MatchingQueuePublisher(QueuePublisher):
    """Publisher for matching queue (from OCR Service)."""

    def publish_for_matching(self, invoice_id: UUID, ocr_data: Dict[str, Any]) -> str:
        """Publish invoice for three-way matching.

        Args:
            invoice_id: ID of the invoice
            ocr_data: OCR extraction data

        Returns:
            Message ID
        """
        message = {
            "invoice_id": str(invoice_id),
            "ocr_data": ocr_data,
        }
        return self.message_queue.publish_message(QueueName.MATCHING_QUEUE.value, message)


class DuplicateDetectionQueuePublisher(QueuePublisher):
    """Publisher for duplicate detection queue (from Matching Service)."""

    def publish_for_duplicate_detection(self, invoice_id: UUID, invoice_data: Dict[str, Any]) -> str:
        """Publish invoice for duplicate detection.

        Args:
            invoice_id: ID of the invoice
            invoice_data: Invoice data

        Returns:
            Message ID
        """
        message = {
            "invoice_id": str(invoice_id),
            "data": invoice_data,
        }
        return self.message_queue.publish_message(QueueName.DUPLICATE_DETECTION_QUEUE.value, message)


class AnomalyDetectionQueuePublisher(QueuePublisher):
    """Publisher for anomaly detection queue (from Duplicate Detection Service)."""

    def publish_for_anomaly_detection(self, invoice_id: UUID, invoice_data: Dict[str, Any]) -> str:
        """Publish invoice for anomaly detection.

        Args:
            invoice_id: ID of the invoice
            invoice_data: Invoice data

        Returns:
            Message ID
        """
        message = {
            "invoice_id": str(invoice_id),
            "data": invoice_data,
        }
        return self.message_queue.publish_message(QueueName.ANOMALY_DETECTION_QUEUE.value, message)


class DecisionQueuePublisher(QueuePublisher):
    """Publisher for decision queue (from Anomaly Detection Service)."""

    def publish_for_decision(self, invoice_id: UUID, invoice_data: Dict[str, Any]) -> str:
        """Publish invoice for decision engine.

        Args:
            invoice_id: ID of the invoice
            invoice_data: Invoice data

        Returns:
            Message ID
        """
        message = {
            "invoice_id": str(invoice_id),
            "data": invoice_data,
        }
        return self.message_queue.publish_message(QueueName.DECISION_QUEUE.value, message)


class LLMQueuePublisher(QueuePublisher):
    """Publisher for LLM queue (from Decision Engine)."""

    def publish_for_llm_explanation(self, exception_id: UUID, exception_data: Dict[str, Any]) -> str:
        """Publish exception for LLM explanation.

        Args:
            exception_id: ID of the exception
            exception_data: Exception data

        Returns:
            Message ID
        """
        message = {
            "exception_id": str(exception_id),
            "data": exception_data,
        }
        return self.message_queue.publish_message(QueueName.LLM_QUEUE.value, message)


class PaymentQueuePublisher(QueuePublisher):
    """Publisher for payment queue (from Decision Engine)."""

    def publish_for_payment_scheduling(self, invoice_id: UUID, invoice_data: Dict[str, Any]) -> str:
        """Publish invoice for payment scheduling.

        Args:
            invoice_id: ID of the invoice
            invoice_data: Invoice data

        Returns:
            Message ID
        """
        message = {
            "invoice_id": str(invoice_id),
            "data": invoice_data,
        }
        return self.message_queue.publish_message(QueueName.PAYMENT_QUEUE.value, message)


class AuditQueuePublisher(QueuePublisher):
    """Publisher for audit queue (from all services)."""

    def publish_audit_event(self, event_type: str, event_data: Dict[str, Any]) -> str:
        """Publish audit event.

        Args:
            event_type: Type of audit event
            event_data: Event data

        Returns:
            Message ID
        """
        message = {
            "event_type": event_type,
            "data": event_data,
        }
        return self.message_queue.publish_message(QueueName.AUDIT_QUEUE.value, message)


class WebSocketBroadcastQueuePublisher(QueuePublisher):
    """Publisher for WebSocket broadcast queue (from all services)."""

    def publish_exception_created(
        self,
        exception_id: UUID,
        exception_data: Dict[str, Any],
        *,
        sequence: Optional[int] = None,
    ) -> str:
        """Publish exception created event.

        Args:
            exception_id: ID of the exception
            exception_data: Exception data (must include invoice_id)
            sequence: Per-invoice ordering sequence for FIFO delivery

        Returns:
            Message ID
        """
        from datetime import datetime, UTC

        message = {
            "event_type": "EXCEPTION_CREATED",
            "exception_id": str(exception_id),
            "data": exception_data,
            "timestamp": exception_data.get("timestamp") or datetime.now(UTC).isoformat(),
            "sequence": sequence,
        }
        return self.message_queue.publish_message(QueueName.WEBSOCKET_BROADCAST_QUEUE.value, message)

    def publish_explanation_ready(
        self,
        exception_id: UUID,
        explanation: str,
        *,
        fallback: bool = False,
        invoice_id: Optional[str] = None,
        sequence: Optional[int] = None,
    ) -> str:
        """Publish explanation ready event.

        Args:
            exception_id: ID of the exception
            explanation: LLM explanation
            fallback: Whether explanation was template-generated
            invoice_id: Invoice ID for ordered delivery
            sequence: Per-invoice ordering sequence for FIFO delivery

        Returns:
            Message ID
        """
        from datetime import datetime, UTC

        message = {
            "event_type": "EXPLANATION_READY",
            "exception_id": str(exception_id),
            "explanation": explanation,
            "fallback": fallback,
            "invoice_id": invoice_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "sequence": sequence,
        }
        return self.message_queue.publish_message(QueueName.WEBSOCKET_BROADCAST_QUEUE.value, message)

    def publish_invoice_status_changed(
        self,
        invoice_id: UUID,
        old_status: str,
        new_status: str,
        *,
        actor_id: Optional[str] = None,
        event_timestamp: Optional[str] = None,
        sequence: Optional[int] = None,
    ) -> str:
        """Publish invoice status changed event.

        Args:
            invoice_id: ID of the invoice
            old_status: Previous status
            new_status: New status
            actor_id: User or system actor that triggered the change
            event_timestamp: ISO 8601 timestamp for the status change
            sequence: Per-invoice ordering sequence for FIFO delivery

        Returns:
            Message ID
        """
        from datetime import datetime, UTC

        message = {
            "event_type": "INVOICE_STATUS_CHANGED",
            "invoice_id": str(invoice_id),
            "old_status": old_status,
            "new_status": new_status,
            "actor_id": actor_id,
            "event_timestamp": event_timestamp or datetime.now(UTC).isoformat(),
            "timestamp": event_timestamp or datetime.now(UTC).isoformat(),
            "sequence": sequence,
        }
        return self.message_queue.publish_message(QueueName.WEBSOCKET_BROADCAST_QUEUE.value, message)
