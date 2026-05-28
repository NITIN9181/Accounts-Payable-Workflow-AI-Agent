"""Exception models for AP Workflow Agent."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, String, DECIMAL, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from ap_workflow.database.session import Base


class SeverityBand(str, Enum):
    """Severity band enumeration."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class InvoiceException(Base):
    """Invoice exception model storing exception details."""

    __tablename__ = "invoice_exceptions"

    exception_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_id = Column(PGUUID(as_uuid=True), ForeignKey("invoices.invoice_id"), nullable=False)
    exception_type = Column(String(50))  # DUPLICATE_EXACT, DUPLICATE_FUZZY, PO_MISMATCH, PO_MISSING, PARTIAL_RECEIPT, RECEIPT_MISSING, INCOMPLETE_DATA
    severity = Column(DECIMAL(3, 2), nullable=False)
    severity_band = Column(String(20))  # CRITICAL, HIGH, MEDIUM, LOW
    details_json = Column(String)  # JSON string for exception details
    llm_explanation = Column(Text)
    llm_explanation_fallback = Column(Boolean, default=False)
    llm_explanation_ready = Column(Boolean, default=False)
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    invoice = relationship("Invoice", back_populates="exceptions")
    approvals = relationship("Approval", back_populates="exception")

    def __repr__(self) -> str:
        return f"<InvoiceException(exception_id={self.exception_id}, invoice_id={self.invoice_id}, exception_type={self.exception_type})>"
