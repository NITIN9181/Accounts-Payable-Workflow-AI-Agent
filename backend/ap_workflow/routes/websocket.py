"""WebSocket routing and connection management for AP Workflow Agent."""

import asyncio
import json
import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Dict
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status

from ap_workflow.core.config import settings
from ap_workflow.core.security import verify_access_token
from ap_workflow.services.message_queue import MessageQueueService, QueueName
from ap_workflow.services.websocket_events import format_queue_message_for_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages active WebSocket connections and ordered broadcasts."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.last_pong: Dict[str, float] = {}
        self._pending_by_invoice: Dict[str, Dict[int, dict]] = defaultdict(dict)
        self._next_expected_seq: Dict[str, int] = defaultdict(lambda: 1)

    async def connect(self, connection_id: str, websocket: WebSocket):
        """Accept connection and register client."""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        self.last_pong[connection_id] = datetime.now(UTC).timestamp()
        logger.info("WebSocket client connected: %s", connection_id)

    def disconnect(self, connection_id: str):
        """Unregister client."""
        self.active_connections.pop(connection_id, None)
        self.last_pong.pop(connection_id, None)
        logger.info("WebSocket client disconnected: %s", connection_id)

    def record_pong(self, connection_id: str):
        """Record the timestamp of the last received PONG."""
        self.last_pong[connection_id] = datetime.now(UTC).timestamp()

    async def _send_to_all(self, message: dict):
        """Send a formatted event to every connected client."""
        message_json = json.dumps(message)
        for connection_id, websocket in list(self.active_connections.items()):
            try:
                await websocket.send_text(message_json)
            except Exception as exc:
                logger.error("Error sending message to %s: %s", connection_id, exc)
                self.disconnect(connection_id)

    async def _flush_invoice_buffer(self, invoice_id: str):
        """Deliver buffered events for an invoice in sequence order."""
        buffer = self._pending_by_invoice.get(invoice_id, {})
        next_seq = self._next_expected_seq[invoice_id]

        while next_seq in buffer:
            event = buffer.pop(next_seq)
            await self._send_to_all(event)
            next_seq += 1
            self._next_expected_seq[invoice_id] = next_seq

        if not buffer:
            self._pending_by_invoice.pop(invoice_id, None)

    async def broadcast(self, message: dict):
        """Broadcast with per-invoice FIFO ordering when sequence is present."""
        invoice_id = message.pop("_invoice_id", None)
        sequence = message.pop("_sequence", None)

        if invoice_id and sequence is not None:
            self._pending_by_invoice[invoice_id][sequence] = message
            await self._flush_invoice_buffer(invoice_id)
            return

        await self._send_to_all(message)


manager = ConnectionManager()


async def send_pings(
    websocket: WebSocket,
    connection_id: str,
    ping_interval: int,
    pong_timeout: int,
):
    """Periodically send PING messages and close if no PONG within timeout."""
    try:
        while True:
            await asyncio.sleep(ping_interval)

            ping_time = datetime.now(UTC).timestamp()

            await websocket.send_json({
                "type": "PING",
                "timestamp": datetime.now(UTC).isoformat(),
            })

            await asyncio.sleep(pong_timeout)

            last_pong_time = manager.last_pong.get(connection_id, 0)
            if last_pong_time < ping_time:
                logger.warning("PING timeout for connection %s. Closing.", connection_id)
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                break
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.error("Error in keep-alive loop for %s: %s", connection_id, exc)


@router.websocket("/ws/stream")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    """WebSocket endpoint for real-time events feed (WS /ws/stream?token=<jwt>)."""
    connection_id = str(uuid.uuid4())

    try:
        verify_access_token(token)
    except ValueError as exc:
        logger.warning("WebSocket connection rejected: %s", exc)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token")
        return

    await manager.connect(connection_id, websocket)

    try:
        await websocket.send_json({
            "type": "CONNECTION_ACK",
            "timestamp": datetime.now(UTC).isoformat(),
            "connection_id": connection_id,
        })
    except Exception as exc:
        logger.error("Failed to send CONNECTION_ACK: %s", exc)
        manager.disconnect(connection_id)
        return

    ping_task = asyncio.create_task(
        send_pings(
            websocket,
            connection_id,
            settings.websocket_ping_interval,
            settings.websocket_pong_timeout,
        )
    )

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "PONG":
                    manager.record_pong(connection_id)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        ping_task.cancel()
        manager.disconnect(connection_id)


async def consume_and_broadcast():
    """Consume websocket_broadcast_queue and broadcast to connected clients."""
    queue_service = MessageQueueService()
    logger.info("Starting WebSocket broadcast queue consumer")
    loop = asyncio.get_running_loop()

    # Check if Redis is available
    if not queue_service.client:
        logger.warning("Redis client not available. WebSocket broadcast consumer disabled.")
        return

    while True:
        try:
            message = await loop.run_in_executor(
                None,
                queue_service.consume_message,
                QueueName.WEBSOCKET_BROADCAST_QUEUE.value,
                5,
            )

            if message:
                client_event = format_queue_message_for_client(message)
                await manager.broadcast(client_event)

        except asyncio.CancelledError:
            logger.info("WebSocket broadcast consumer cancelled")
            break
        except Exception as exc:
            logger.error("WebSocket broadcast consumer error: %s", exc)
            await asyncio.sleep(1)
