"""Message queue service for AP Workflow Agent."""

import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from enum import Enum

from ap_workflow.redis.client import redis_client

logger = logging.getLogger(__name__)


class QueueName(str, Enum):
    """Message queue names."""

    INVOICE_QUEUE = "invoice_queue"
    MATCHING_QUEUE = "matching_queue"
    DUPLICATE_DETECTION_QUEUE = "duplicate_detection_queue"
    ANOMALY_DETECTION_QUEUE = "anomaly_detection_queue"
    DECISION_QUEUE = "decision_queue"
    LLM_QUEUE = "llm_queue"
    PAYMENT_QUEUE = "payment_queue"
    AUDIT_QUEUE = "audit_queue"
    WEBSOCKET_BROADCAST_QUEUE = "websocket_broadcast_queue"
    DEAD_LETTER_QUEUE = "dead_letter_queue"


class MessageQueueService:
    """Service for managing message queues with retry logic."""

    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 2, 4]  # Exponential backoff: 1s, 2s, 4s

    def __init__(self):
        """Initialize message queue service."""
        self.client = redis_client.client

    def publish_message(
        self,
        queue_name: str,
        message: Dict[str, Any],
        priority: int = 0,
    ) -> str:
        """Publish a message to a queue.

        Args:
            queue_name: Name of the queue
            message: Message payload
            priority: Priority level (higher = more urgent)

        Returns:
            Message ID
        """
        try:
            # Add metadata
            message_id = f"{queue_name}:{datetime.utcnow().timestamp()}"
            message_with_metadata = {
                "id": message_id,
                "queue": queue_name,
                "payload": message,
                "priority": priority,
                "created_at": datetime.utcnow().isoformat(),
                "retries": 0,
            }

            # Serialize and publish
            message_json = json.dumps(message_with_metadata)
            self.client.rpush(queue_name, message_json)

            logger.info(f"Published message {message_id} to {queue_name}")
            return message_id

        except Exception as e:
            logger.error(f"Error publishing message to {queue_name}: {str(e)}")
            raise

    def consume_message(self, queue_name: str, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """Consume a message from a queue (blocking).

        Args:
            queue_name: Name of the queue
            timeout: Timeout in seconds (0 = blocking indefinitely)

        Returns:
            Message payload or None if timeout
        """
        try:
            result = self.client.blpop(queue_name, timeout=timeout)
            if result:
                _, message_json = result
                message_data = json.loads(message_json)
                logger.info(f"Consumed message {message_data['id']} from {queue_name}")
                return message_data
            return None

        except Exception as e:
            logger.error(f"Error consuming message from {queue_name}: {str(e)}")
            raise

    def retry_message(
        self,
        message: Dict[str, Any],
        queue_name: str,
        error: Optional[str] = None,
    ) -> bool:
        """Retry a failed message with exponential backoff.

        Args:
            message: Message to retry
            queue_name: Name of the queue
            error: Error message

        Returns:
            True if retried, False if max retries exceeded
        """
        try:
            retries = message.get("retries", 0)

            if retries >= self.MAX_RETRIES:
                # Move to dead letter queue
                self._move_to_dead_letter_queue(message, error)
                logger.warning(f"Message {message['id']} moved to DLQ after {retries} retries")
                return False

            # Calculate backoff delay
            delay_seconds = self.RETRY_DELAYS[retries]

            # Update retry count
            message["retries"] = retries + 1
            message["last_error"] = error
            message["last_retry_at"] = datetime.utcnow().isoformat()

            # Re-publish with delay
            message_json = json.dumps(message)
            self.client.rpush(queue_name, message_json)

            logger.info(
                f"Retrying message {message['id']} (attempt {retries + 1}/{self.MAX_RETRIES}) "
                f"with {delay_seconds}s delay"
            )
            return True

        except Exception as e:
            logger.error(f"Error retrying message: {str(e)}")
            raise

    def _move_to_dead_letter_queue(
        self,
        message: Dict[str, Any],
        error: Optional[str] = None,
    ) -> None:
        """Move a message to the dead letter queue.

        Args:
            message: Message to move
            error: Error message
        """
        try:
            message["moved_to_dlq_at"] = datetime.utcnow().isoformat()
            message["dlq_error"] = error

            message_json = json.dumps(message)
            self.client.rpush(QueueName.DEAD_LETTER_QUEUE.value, message_json)

            logger.warning(f"Message {message['id']} moved to DLQ: {error}")

        except Exception as e:
            logger.error(f"Error moving message to DLQ: {str(e)}")

    def get_queue_depth(self, queue_name: str) -> int:
        """Get the number of messages in a queue.

        Args:
            queue_name: Name of the queue

        Returns:
            Number of messages in queue
        """
        try:
            return self.client.llen(queue_name)
        except Exception as e:
            logger.error(f"Error getting queue depth for {queue_name}: {str(e)}")
            return 0

    def get_queue_stats(self) -> Dict[str, int]:
        """Get statistics for all queues.

        Returns:
            Dictionary with queue names and message counts
        """
        stats = {}
        for queue in QueueName:
            stats[queue.value] = self.get_queue_depth(queue.value)
        return stats

    def clear_queue(self, queue_name: str) -> int:
        """Clear all messages from a queue.

        Args:
            queue_name: Name of the queue

        Returns:
            Number of messages cleared
        """
        try:
            count = self.client.llen(queue_name)
            self.client.delete(queue_name)
            logger.info(f"Cleared {count} messages from {queue_name}")
            return count
        except Exception as e:
            logger.error(f"Error clearing queue {queue_name}: {str(e)}")
            return 0

    def peek_message(self, queue_name: str, index: int = 0) -> Optional[Dict[str, Any]]:
        """Peek at a message in a queue without consuming it.

        Args:
            queue_name: Name of the queue
            index: Index of message to peek (0 = first)

        Returns:
            Message payload or None if not found
        """
        try:
            message_json = self.client.lindex(queue_name, index)
            if message_json:
                return json.loads(message_json)
            return None
        except Exception as e:
            logger.error(f"Error peeking at message in {queue_name}: {str(e)}")
            return None

    def get_dead_letter_messages(self, limit: int = 100) -> list:
        """Get messages from the dead letter queue.

        Args:
            limit: Maximum number of messages to retrieve

        Returns:
            List of messages in DLQ
        """
        try:
            messages = []
            for i in range(limit):
                message_json = self.client.lindex(QueueName.DEAD_LETTER_QUEUE.value, i)
                if message_json:
                    messages.append(json.loads(message_json))
                else:
                    break
            return messages
        except Exception as e:
            logger.error(f"Error retrieving DLQ messages: {str(e)}")
            return []
