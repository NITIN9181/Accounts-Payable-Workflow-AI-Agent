"""Message queue consumers for AP Workflow Agent."""

import logging
from typing import Callable, Optional
from sqlalchemy.orm import Session

from ap_workflow.services.message_queue import MessageQueueService, QueueName

logger = logging.getLogger(__name__)


class QueueConsumer:
    """Base class for queue consumers."""

    def __init__(self, queue_name: str, db_session: Session):
        """Initialize queue consumer.

        Args:
            queue_name: Name of the queue to consume from
            db_session: Database session
        """
        self.queue_name = queue_name
        self.db_session = db_session
        self.message_queue = MessageQueueService()

    def start_consuming(self, handler: Callable, timeout: int = 0) -> None:
        """Start consuming messages from the queue.

        Args:
            handler: Callback function to handle messages
            timeout: Timeout in seconds (0 = blocking indefinitely)
        """
        logger.info(f"Starting consumer for {self.queue_name}")

        while True:
            try:
                message = self.message_queue.consume_message(self.queue_name, timeout=timeout)

                if message:
                    try:
                        # Call handler with message payload
                        handler(message["payload"])
                        logger.info(f"Successfully processed message {message['id']}")

                    except Exception as e:
                        logger.error(f"Error processing message {message['id']}: {str(e)}")

                        # Retry with exponential backoff
                        if not self.message_queue.retry_message(message, self.queue_name, str(e)):
                            logger.error(f"Message {message['id']} failed after max retries")

            except KeyboardInterrupt:
                logger.info(f"Stopping consumer for {self.queue_name}")
                break

            except Exception as e:
                logger.error(f"Error in consumer loop: {str(e)}")

    def stop_consuming(self) -> None:
        """Stop consuming messages."""
        logger.info(f"Stopping consumer for {self.queue_name}")


class InvoiceQueueConsumer(QueueConsumer):
    """Consumer for invoice queue (OCR Service)."""

    def __init__(self, db_session: Session):
        """Initialize invoice queue consumer."""
        super().__init__(QueueName.INVOICE_QUEUE.value, db_session)


class MatchingQueueConsumer(QueueConsumer):
    """Consumer for matching queue (Matching Service)."""

    def __init__(self, db_session: Session):
        """Initialize matching queue consumer."""
        super().__init__(QueueName.MATCHING_QUEUE.value, db_session)


class DuplicateDetectionQueueConsumer(QueueConsumer):
    """Consumer for duplicate detection queue (Duplicate Detection Service)."""

    def __init__(self, db_session: Session):
        """Initialize duplicate detection queue consumer."""
        super().__init__(QueueName.DUPLICATE_DETECTION_QUEUE.value, db_session)


class AnomalyDetectionQueueConsumer(QueueConsumer):
    """Consumer for anomaly detection queue (Anomaly Detection Service)."""

    def __init__(self, db_session: Session):
        """Initialize anomaly detection queue consumer."""
        super().__init__(QueueName.ANOMALY_DETECTION_QUEUE.value, db_session)


class DecisionQueueConsumer(QueueConsumer):
    """Consumer for decision queue (Decision Engine)."""

    def __init__(self, db_session: Session):
        """Initialize decision queue consumer."""
        super().__init__(QueueName.DECISION_QUEUE.value, db_session)


class LLMQueueConsumer(QueueConsumer):
    """Consumer for LLM queue (LLM Explainer Service)."""

    def __init__(self, db_session: Session):
        """Initialize LLM queue consumer."""
        super().__init__(QueueName.LLM_QUEUE.value, db_session)


class PaymentQueueConsumer(QueueConsumer):
    """Consumer for payment queue (Payment Scheduler)."""

    def __init__(self, db_session: Session):
        """Initialize payment queue consumer."""
        super().__init__(QueueName.PAYMENT_QUEUE.value, db_session)


class AuditQueueConsumer(QueueConsumer):
    """Consumer for audit queue (Audit Logger)."""

    def __init__(self, db_session: Session):
        """Initialize audit queue consumer."""
        super().__init__(QueueName.AUDIT_QUEUE.value, db_session)


class WebSocketBroadcastQueueConsumer(QueueConsumer):
    """Consumer for WebSocket broadcast queue (WebSocket Server)."""

    def __init__(self, db_session: Session):
        """Initialize WebSocket broadcast queue consumer."""
        super().__init__(QueueName.WEBSOCKET_BROADCAST_QUEUE.value, db_session)
