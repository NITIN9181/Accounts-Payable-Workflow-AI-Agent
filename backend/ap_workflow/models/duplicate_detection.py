"""Duplicate detection models for AP Workflow Agent."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, String, DECIMAL, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from ap_workflow.database.session import Base


class DuplicateDetection(Base):
    """Duplicate detection model storing duplicate invoice relationships."""

    __tablename__ = "duplicate_detections"

    duplicate_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_id = Column(PGUUID(as_uuid=True), ForeignKey("invoices.invoice_id"), nullable=False)
    duplicate_of_invoice_id = Column(PGUUID(as_uuid=True), ForeignKey("invoices.invoice_id"))
    detection_type = Column(String(20))  # EXACT, FUZZY
    fuzzy_confidence = Column(DECIMAL(3, 2))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    invoice = relationship("Invoice", foreign_keys=[invoice_id], back_populates="duplicate_detections")
    duplicate_of = relationship("Invoice", foreign_keys=[duplicate_of_invoice_id], remote_side="Invoice.invoice_id")

    def __repr__(self) -> str:
        return f"<DuplicateDetection(duplicate_id={self.duplicate_id}, invoice_id={self.invoice_id}, detection_type={self.detection_type})>"
