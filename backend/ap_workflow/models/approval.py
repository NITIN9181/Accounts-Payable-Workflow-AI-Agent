"""Approval models for AP Workflow Agent."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from ap_workflow.database.session import Base


class ApprovalStatus(str, Enum):
    """Approval status enumeration."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"


class ApprovalQueue(str, Enum):
    """Approval queue enumeration."""

    AP_CLERK_QUEUE = "AP_CLERK_QUEUE"
    MANAGER_QUEUE = "MANAGER_QUEUE"
    CFO_ESCALATION_QUEUE = "CFO_ESCALATION_QUEUE"


class Approval(Base):
    """Approval model storing approval records."""

    __tablename__ = "approvals"

    approval_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_id = Column(PGUUID(as_uuid=True), ForeignKey("invoices.invoice_id"), nullable=False)
    exception_id = Column(PGUUID(as_uuid=True), ForeignKey("invoice_exceptions.exception_id"))
    approver_id = Column(PGUUID(as_uuid=True))
    approver_role = Column(String(50))  # AP_CLERK, MANAGER, CFO
    approval_queue = Column(String(50))  # AP_CLERK_QUEUE, MANAGER_QUEUE, CFO_ESCALATION_QUEUE
    status = Column(String(50), default=ApprovalStatus.PENDING)
    sla_deadline = Column(DateTime, nullable=False)
    sla_violated = Column(Boolean, default=False)
    notes = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    # Relationships
    invoice = relationship("Invoice", back_populates="approvals")
    exception = relationship("InvoiceException", back_populates="approvals")

    def __repr__(self) -> str:
        return f"<Approval(approval_id={self.approval_id}, invoice_id={self.invoice_id}, status={self.status})>"
