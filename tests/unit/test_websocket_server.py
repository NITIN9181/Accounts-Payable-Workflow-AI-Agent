"""Unit tests for WebSocket server authentication and event formatting."""

import json
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ap_workflow.core.security import create_access_token, verify_access_token
from ap_workflow.routes.websocket import router as websocket_router
from ap_workflow.services.websocket_events import format_queue_message_for_client


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(websocket_router)
    return TestClient(app)


class TestJWTSecurity:
    def test_create_and_verify_token(self):
        token = create_access_token("user-123", role="AP_CLERK")
        payload = verify_access_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "AP_CLERK"

    def test_expired_token_rejected(self):
        token = create_access_token(
            "user-123",
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(ValueError, match="Token validation failed"):
            verify_access_token(token)

    def test_empty_token_rejected(self):
        with pytest.raises(ValueError, match="Token is empty"):
            verify_access_token("")


class TestWebSocketEndpoint:
    def test_connection_ack_with_valid_token(self, client):
        token = create_access_token("analyst-1", role="AP_CLERK")
        with client.websocket_connect(f"/ws/stream?token={token}") as ws:
            data = ws.receive_json()
            assert data["type"] == "CONNECTION_ACK"
            assert "timestamp" in data
            assert "connection_id" in data

    def test_invalid_token_rejected(self, client):
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/stream?token=not-a-valid-jwt"):
                pass

    def test_pong_recorded(self, client):
        token = create_access_token("analyst-1")
        with client.websocket_connect(f"/ws/stream?token={token}") as ws:
            ws.receive_json()  # CONNECTION_ACK
            ws.send_json({"type": "PONG"})


class TestEventFormatting:
    def test_exception_created_format(self):
        queue_msg = {
            "created_at": "2026-05-27T12:00:00+00:00",
            "payload": {
                "event_type": "EXCEPTION_CREATED",
                "exception_id": "exc-1",
                "data": {
                    "invoice_id": "inv-1",
                    "vendor_name": "Acme",
                    "total_amount": 100.0,
                    "final_severity": 0.85,
                    "severity_band": "HIGH",
                    "exception_type": "ANOMALY",
                    "llm_explanation": None,
                    "llm_explanation_ready": False,
                },
            },
        }
        event = format_queue_message_for_client(queue_msg)
        assert event["type"] == "EXCEPTION_CREATED"
        assert event["payload"]["exception_id"] == "exc-1"
        assert event["payload"]["invoice_id"] == "inv-1"
        assert event["_sequence"] is None

    def test_invoice_status_changed_format(self):
        queue_msg = {
            "created_at": "2026-05-27T12:00:00+00:00",
            "payload": {
                "event_type": "INVOICE_STATUS_CHANGED",
                "invoice_id": "inv-1",
                "old_status": "PENDING_APPROVAL",
                "new_status": "APPROVED",
                "actor_id": "SYSTEM",
                "sequence": 2,
            },
        }
        event = format_queue_message_for_client(queue_msg)
        assert event["type"] == "INVOICE_STATUS_CHANGED"
        assert event["payload"]["new_status"] == "APPROVED"
        assert event["_sequence"] == 2
