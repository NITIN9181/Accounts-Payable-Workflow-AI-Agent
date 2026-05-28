"""OCR extraction models for AP Workflow Agent."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, String, DECIMAL, Date, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship

from ap_workflow.database.session import Base


class OCRExtraction(Base):
    """OCR extraction model storing extracted invoice fields."""

    __tablename__ = "ocr_extractions"

    extraction_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_id = Column(PGUUID(as_uuid=True), ForeignKey("invoices.invoice_id"), nullable=False, unique=True)
    invoice_number = Column(String(50))
    invoice_number_confidence = Column(DECIMAL(3, 2))
    vendor_name = Column(String(100))
    vendor_name_confidence = Column(DECIMAL(3, 2))
    total_amount = Column(DECIMAL(12, 2))
    total_amount_confidence = Column(DECIMAL(3, 2))
    tax_amount = Column(DECIMAL(12, 2))
    tax_amount_confidence = Column(DECIMAL(3, 2))
    invoice_date = Column(Date)
    invoice_date_confidence = Column(DECIMAL(3, 2))
    due_date = Column(Date)
    due_date_confidence = Column(DECIMAL(3, 2))
    po_reference = Column(String(50))
    po_reference_confidence = Column(DECIMAL(3, 2))
    ocr_raw_json = Column(JSONB)  # Full OCR output with bounding boxes
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    invoice = relationship("Invoice", back_populates="ocr_extraction")

    def __repr__(self) -> str:
        return f"<OCRExtraction(extraction_id={self.extraction_id}, invoice_id={self.invoice_id})>"
