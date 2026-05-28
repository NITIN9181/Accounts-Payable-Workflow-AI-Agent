"""Matching models for AP Workflow Agent."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, String, DECIMAL, Date, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship

from ap_workflow.database.session import Base


class PurchaseOrder(Base):
    """Purchase Order model."""

    __tablename__ = "purchase_orders"

    po_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    vendor_key = Column(String(100), nullable=False, index=True)
    po_number = Column(String(50), nullable=False)
    po_date = Column(Date, nullable=False)
    status = Column(String(50))  # OPEN, PARTIALLY_RECEIVED, CLOSED
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    line_items = relationship("POLineItem", back_populates="po", cascade="all, delete-orphan")
    receipts = relationship("Receipt", back_populates="po", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<PurchaseOrder(po_id={self.po_id}, vendor_key={self.vendor_key}, po_number={self.po_number})>"


class POLineItem(Base):
    """Purchase Order line item model."""

    __tablename__ = "po_line_items"

    po_line_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    po_id = Column(PGUUID(as_uuid=True), ForeignKey("purchase_orders.po_id"), nullable=False)
    line_number = Column(Integer)
    sku = Column(String(50))
    description = Column(String(255))
    quantity = Column(DECIMAL(12, 4))
    unit_price = Column(DECIMAL(12, 2))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    po = relationship("PurchaseOrder", back_populates="line_items")
    receipt_line_items = relationship("ReceiptLineItem", back_populates="po_line_item", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<POLineItem(po_line_id={self.po_line_id}, po_id={self.po_id})>"


class Receipt(Base):
    """Receipt model."""

    __tablename__ = "receipts"

    receipt_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    po_id = Column(PGUUID(as_uuid=True), ForeignKey("purchase_orders.po_id"), nullable=False)
    receipt_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    po = relationship("PurchaseOrder", back_populates="receipts")
    line_items = relationship("ReceiptLineItem", back_populates="receipt", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Receipt(receipt_id={self.receipt_id}, po_id={self.po_id})>"


class ReceiptLineItem(Base):
    """Receipt line item model."""

    __tablename__ = "receipt_line_items"

    receipt_line_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    receipt_id = Column(PGUUID(as_uuid=True), ForeignKey("receipts.receipt_id"), nullable=False)
    po_line_id = Column(PGUUID(as_uuid=True), ForeignKey("po_line_items.po_line_id"), nullable=False)
    received_quantity = Column(DECIMAL(12, 4))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    receipt = relationship("Receipt", back_populates="line_items")
    po_line_item = relationship("POLineItem", back_populates="receipt_line_items")

    def __repr__(self) -> str:
        return f"<ReceiptLineItem(receipt_line_id={self.receipt_line_id}, receipt_id={self.receipt_id})>"


class MatchingResult(Base):
    """Matching result model storing three-way match results."""

    __tablename__ = "matching_results"

    matching_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_id = Column(PGUUID(as_uuid=True), ForeignKey("invoices.invoice_id"), nullable=False, unique=True)
    po_id = Column(PGUUID(as_uuid=True), ForeignKey("purchase_orders.po_id"))
    match_status = Column(String(50))  # PO_MATCHED, PO_MISMATCH, PO_MISSING, PARTIAL_RECEIPT, RECEIPT_MISSING, INCOMPLETE_DATA
    variance_details = Column(JSONB)  # {line_item_id, variance_type, variance_amount}
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    invoice = relationship("Invoice", back_populates="matching_results")
    po = relationship("PurchaseOrder")

    def __repr__(self) -> str:
        return f"<MatchingResult(matching_id={self.matching_id}, invoice_id={self.invoice_id}, match_status={self.match_status})>"
