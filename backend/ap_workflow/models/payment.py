"""Payment models for AP Workflow Agent."""

from datetime import datetime, date
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, String, DECIMAL, Date, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from ap_workflow.database.session import Base


class PaymentMethod(str, Enum):
    """Payment method enumeration."""

    ACH = "ACH"
    WIRE = "WIRE"
    CHECK = "CHECK"


class Payment(Base):
    """Payment model storing payment records."""

    __tablename__ = "payments"

    payment_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_id = Column(PGUUID(as_uuid=True), ForeignKey("invoices.invoice_id"), nullable=False)
    scheduled_payment_date = Column(Date, nullable=False)
    payment_method = Column(String(50))  # ACH, WIRE, CHECK
    payment_amount = Column(DECIMAL(12, 2), nullable=False)
    discount_captured = Column(DECIMAL(12, 2))
    status = Column(String(50), default="SCHEDULED")  # SCHEDULED, EXECUTED, FAILED
    created_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime)

    # Relationships
    invoice = relationship("Invoice", back_populates="payments")

    def __repr__(self) -> str:
        return f"<Payment(payment_id={self.payment_id}, invoice_id={self.invoice_id}, scheduled_payment_date={self.scheduled_payment_date})>"


class PaymentBatch(Base):
    """Payment batch model storing aggregated payment batches."""

    __tablename__ = "payment_batches"

    batch_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    scheduled_payment_date = Column(Date, nullable=False)
    total_outflow = Column(DECIMAL(14, 2))
    invoice_count = Column(Integer)
    status = Column(String(50), default="PENDING")  # PENDING, EXECUTED
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<PaymentBatch(batch_id={self.batch_id}, scheduled_payment_date={self.scheduled_payment_date}, invoice_count={self.invoice_count})>"
