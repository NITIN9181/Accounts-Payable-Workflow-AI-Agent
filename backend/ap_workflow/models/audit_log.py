"""Audit log models for AP Workflow Agent."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import event
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship

from ap_workflow.database.session import Base


class AuditAction(str, Enum):
    """Audit action enumeration."""

    INVOICE_CREATED = "invoice_created"
    OCR_EXTRACTION_COMPLETED = "ocr_extraction_completed"
    THREE_WAY_MATCH_PERFORMED = "three_way_match_performed"
    EXCEPTION_CREATED = "exception_created"
    EXCEPTION_RESOLVED = "exception_resolved"
    APPROVAL_ACTION_TAKEN = "approval_action_taken"
    PAYMENT_SCHEDULED = "payment_scheduled"
    INVOICE_STATUS_CHANGED = "invoice_status_changed"
    VENDOR_BASELINE_UPDATED = "vendor_baseline_updated"
    APPROVAL_CREATED = "approval_created"
    APPROVAL_COMPLETED = "approval_completed"
    PAYMENT_EXECUTED = "payment_executed"
    LOW_CONFIDENCE_FIELD_FLAGGED = "low_confidence_field_flagged"


class AuditEntityType(str, Enum):
    """Audit entity type enumeration."""

    INVOICE = "INVOICE"
    EXCEPTION = "EXCEPTION"
    APPROVAL = "APPROVAL"
    PAYMENT = "PAYMENT"
    VENDOR_BASELINE = "VENDOR_BASELINE"


class AuditActorType(str, Enum):
    """Audit actor type enumeration."""

    ANALYST = "ANALYST"
    SYSTEM = "SYSTEM"
    API = "API"
    VENDOR = "VENDOR"


class AuditLog(Base):
    """Audit log model storing immutable system events."""

    __tablename__ = "audit_logs"

    log_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    actor_id = Column(PGUUID(as_uuid=True))
    actor_type = Column(String(50))  # ANALYST, SYSTEM, API, VENDOR
    action_type = Column(String(50))  # See AuditAction enum
    entity_type = Column(String(50))  # See AuditEntityType enum
    entity_id = Column(PGUUID(as_uuid=True))
    before_state = Column(JSONB)  # JSON snapshot of before state
    after_state = Column(JSONB)  # JSON snapshot of after state
    ip_address = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships - note: entity_id is polymorphic, so we use a custom join condition
    # Don't define a back_populates here since it's not a traditional FK

    def __repr__(self) -> str:
        return f"<AuditLog(log_id={self.log_id}, action_type={self.action_type}, entity_id={self.entity_id})>"


@event.listens_for(AuditLog, "before_update", propagate=True)
def _audit_log_before_update(mapper, connection, target) -> None:
    raise ValueError("Audit logs are immutable and cannot be updated")


@event.listens_for(AuditLog, "before_delete", propagate=True)
def _audit_log_before_delete(mapper, connection, target) -> None:
    raise ValueError("Audit logs are immutable and cannot be deleted")
