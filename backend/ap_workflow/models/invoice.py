"""Invoice models for AP Workflow Agent."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    String,
    DECIMAL,
    Date,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    Enum as SQLEnum,
    Integer,
    and_,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship

from ap_workflow.database.session import Base


class InvoiceStatus(str, Enum):
    """Invoice status enumeration."""

    PENDING_OCR = "PENDING_OCR"
    PENDING_INGESTION_QUEUE = "PENDING_INGESTION_QUEUE"
    OCR_FAILED = "OCR_FAILED"
    PENDING_MANUAL_REVIEW = "PENDING_MANUAL_REVIEW"
    PENDING_MATCHING = "PENDING_MATCHING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    HELD = "HELD"
    REJECTED = "REJECTED"
    SCHEDULED = "SCHEDULED"
    PAID = "PAID"
    INGESTION_FAILED = "INGESTION_FAILED"


class Invoice(Base):
    """Invoice model representing a vendor invoice."""

    __tablename__ = "invoices"

    invoice_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    vendor_key = Column(String(100), nullable=False, index=True)
    vendor_name = Column(String(100), nullable=False)
    invoice_number = Column(String(50), nullable=False)
    total_amount = Column(DECIMAL(12, 2), nullable=False)
    total_amount_usd = Column(DECIMAL(12, 2))
    tax_amount = Column(DECIMAL(12, 2))
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    po_reference = Column(String(50))
    currency_code = Column(String(3), default="USD")
    fx_rate = Column(DECIMAL(10, 6))
    stale_fx_rate = Column(Boolean, default=False)
    file_hash = Column(String(64), nullable=False, unique=True)
    file_path = Column(String(255))
    ingestion_source = Column(String(20))  # email|upload|webhook|manual
    status = Column(SQLEnum(InvoiceStatus), default=InvoiceStatus.PENDING_OCR)
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ocr_completed_at = Column(DateTime)
    matching_completed_at = Column(DateTime)
    anomaly_completed_at = Column(DateTime)
    approved_at = Column(DateTime)
    paid_at = Column(DateTime)
    demo_mode = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    ocr_extraction = relationship("OCRExtraction", back_populates="invoice", uselist=False)
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan")
    matching_results = relationship("MatchingResult", back_populates="invoice", cascade="all, delete-orphan")
    duplicate_detections = relationship("DuplicateDetection", foreign_keys="DuplicateDetection.invoice_id", back_populates="invoice", cascade="all, delete-orphan")
    anomaly_detections = relationship("AnomalyDetection", back_populates="invoice", cascade="all, delete-orphan")
    exceptions = relationship("InvoiceException", back_populates="invoice", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", foreign_keys="AuditLog.entity_id", primaryjoin="and_(Invoice.invoice_id==AuditLog.entity_id, AuditLog.entity_type=='INVOICE')", viewonly=True)

    def __repr__(self) -> str:
        return f"<Invoice(invoice_id={self.invoice_id}, vendor_key={self.vendor_key}, invoice_number={self.invoice_number})>"


class InvoiceLineItem(Base):
    """Invoice line item model."""

    __tablename__ = "invoice_line_items"

    line_item_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_id = Column(PGUUID(as_uuid=True), ForeignKey("invoices.invoice_id"), nullable=False)
    description = Column(String(255))
    quantity = Column(DECIMAL(12, 4))
    unit_price = Column(DECIMAL(12, 2))
    line_total = Column(DECIMAL(12, 2))
    sku = Column(String(50))
    po_line_number = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    invoice = relationship("Invoice", back_populates="line_items")

    def __repr__(self) -> str:
        return f"<InvoiceLineItem(line_item_id={self.line_item_id}, invoice_id={self.invoice_id})>"
