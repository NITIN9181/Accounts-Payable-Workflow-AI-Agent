"""WebSocket event formatting and publishing helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Dict, Optional, Union
from uuid import UUID

from ap_workflow.models.exception import InvoiceException
from ap_workflow.models.invoice import Invoice
from ap_workflow.services.queue_publishers import WebSocketBroadcastQueuePublisher

_publisher: Optional[WebSocketBroadcastQueuePublisher] = None
_invoice_sequence: Dict[str, int] = {}


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _get_publisher() -> WebSocketBroadcastQueuePublisher:
    global _publisher
    if _publisher is None:
        _publisher = WebSocketBroadcastQueuePublisher()
    return _publisher


def _next_invoice_sequence(invoice_id: Union[str, UUID]) -> int:
    key = str(invoice_id)
    _invoice_sequence[key] = _invoice_sequence.get(key, 0) + 1
    return _invoice_sequence[key]


def _decimal_to_float(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def format_queue_message_for_client(queue_message: Dict[str, Any]) -> Dict[str, Any]:
    """Transform an internal queue message into a client-facing WebSocket event."""
    inner = queue_message.get("payload") or {}
    event_type = inner.get("event_type")
    timestamp = inner.get("timestamp") or queue_message.get("created_at") or _utc_now_iso()

    if event_type == "EXCEPTION_CREATED":
        data = inner.get("data") or {}
        return {
            "type": "EXCEPTION_CREATED",
            "timestamp": timestamp,
            "payload": {
                "exception_id": inner.get("exception_id"),
                "invoice_id": data.get("invoice_id"),
                "vendor_name": data.get("vendor_name"),
                "total_amount": data.get("total_amount"),
                "final_severity": data.get("final_severity"),
                "severity_band": data.get("severity_band"),
                "exception_type": data.get("exception_type"),
                "llm_explanation": data.get("llm_explanation"),
                "llm_explanation_ready": data.get("llm_explanation_ready", False),
            },
            "_invoice_id": data.get("invoice_id"),
            "_sequence": inner.get("sequence"),
        }

    if event_type == "EXPLANATION_READY":
        return {
            "type": "EXPLANATION_READY",
            "timestamp": timestamp,
            "payload": {
                "exception_id": inner.get("exception_id"),
                "llm_explanation": inner.get("explanation"),
                "fallback": inner.get("fallback", False),
            },
            "_invoice_id": inner.get("invoice_id"),
            "_sequence": inner.get("sequence"),
        }

    if event_type == "INVOICE_STATUS_CHANGED":
        return {
            "type": "INVOICE_STATUS_CHANGED",
            "timestamp": timestamp,
            "payload": {
                "invoice_id": inner.get("invoice_id"),
                "old_status": inner.get("old_status"),
                "new_status": inner.get("new_status"),
                "actor_id": inner.get("actor_id"),
                "timestamp": inner.get("event_timestamp") or timestamp,
            },
            "_invoice_id": inner.get("invoice_id"),
            "_sequence": inner.get("sequence"),
        }

    return {
        "type": event_type or "UNKNOWN",
        "timestamp": timestamp,
        "payload": inner,
    }


def publish_exception_created(
    exception: InvoiceException,
    invoice: Invoice,
) -> Optional[str]:
    """Publish EXCEPTION_CREATED when severity > 0.4."""
    severity = float(exception.severity)
    if severity <= 0.4:
        return None

    invoice_id = str(invoice.invoice_id)
    exception_data = {
        "invoice_id": invoice_id,
        "vendor_name": invoice.vendor_name,
        "total_amount": _decimal_to_float(invoice.total_amount_usd or invoice.total_amount),
        "final_severity": severity,
        "severity_band": exception.severity_band,
        "exception_type": exception.exception_type,
        "llm_explanation": exception.llm_explanation,
        "llm_explanation_ready": bool(exception.llm_explanation_ready),
        "timestamp": _utc_now_iso(),
    }

    return _get_publisher().publish_exception_created(
        exception.exception_id,
        exception_data,
        sequence=_next_invoice_sequence(invoice_id),
    )


def publish_explanation_ready(
    exception: InvoiceException,
    *,
    invoice_id: Optional[UUID] = None,
) -> Optional[str]:
    """Publish EXPLANATION_READY when an explanation becomes available."""
    if not exception.llm_explanation:
        return None

    inv_id = str(invoice_id or exception.invoice_id)
    return _get_publisher().publish_explanation_ready(
        exception.exception_id,
        exception.llm_explanation,
        fallback=bool(exception.llm_explanation_fallback),
        invoice_id=inv_id,
        sequence=_next_invoice_sequence(inv_id),
    )


def publish_invoice_status_changed(
    invoice_id: Union[str, UUID],
    old_status: str,
    new_status: str,
    *,
    actor_id: Optional[str] = None,
) -> str:
    """Publish INVOICE_STATUS_CHANGED for a status transition."""
    inv_id = str(invoice_id)
    return _get_publisher().publish_invoice_status_changed(
        invoice_id,
        old_status,
        new_status,
        actor_id=actor_id,
        event_timestamp=_utc_now_iso(),
        sequence=_next_invoice_sequence(inv_id),
    )
