"""Invoice Pydantic schemas for AP Workflow Agent."""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator, ConfigDict
from uuid import UUID

from ap_workflow.models.invoice import InvoiceStatus


class InvoiceLineItemBase(BaseModel):
    """Base invoice line item schema."""

    description: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    line_total: Optional[Decimal] = None
    sku: Optional[str] = None
    po_line_number: Optional[int] = None


class InvoiceLineItemCreate(InvoiceLineItemBase):
    """Schema for creating invoice line items."""

    pass


class InvoiceLineItemResponse(InvoiceLineItemBase):
    """Schema for invoice line item response."""

    line_item_id: UUID
    invoice_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceBase(BaseModel):
    """Base invoice schema."""

    vendor_key: str = Field(..., min_length=1, max_length=100)
    vendor_name: str = Field(..., min_length=1, max_length=100)
    invoice_number: str = Field(..., min_length=1, max_length=50)
    total_amount: Decimal = Field(..., gt=0, le=999999.99)
    total_amount_usd: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    invoice_date: date
    due_date: date
    po_reference: Optional[str] = Field(None, max_length=50)
    currency_code: Optional[str] = Field(default="USD", max_length=3)
    fx_rate: Optional[Decimal] = None
    stale_fx_rate: Optional[bool] = False
    file_hash: Optional[str] = Field(None, max_length=64)
    file_path: Optional[str] = None
    ingestion_source: Optional[str] = None
    status: Optional[InvoiceStatus] = InvoiceStatus.PENDING_OCR
    received_at: Optional[datetime] = None
    ocr_completed_at: Optional[datetime] = None
    matching_completed_at: Optional[datetime] = None
    anomaly_completed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    demo_mode: Optional[bool] = False

    @field_validator("invoice_number")
    @classmethod
    def invoice_number_must_be_alphanumeric(cls, v: str) -> str:
        """Validate invoice_number is alphanumeric (letters, digits, hyphens, underscores)."""
        if not re.match(r"^[a-zA-Z0-9\-_]+$", v):
            raise ValueError("invoice_number must be alphanumeric (letters, digits, hyphens, underscores)")
        return v

    @field_validator("vendor_name")
    @classmethod
    def vendor_name_must_be_valid(cls, v: str) -> str:
        """Validate vendor_name contains only valid characters."""
        # Allow letters, digits, spaces, hyphens, periods, commas, and ampersands
        if not re.match(r"^[a-zA-Z0-9\s\-.,&']+$", v):
            raise ValueError("vendor_name contains invalid characters")
        return v

    @field_validator("total_amount")
    @classmethod
    def total_amount_must_be_positive(cls, v: Decimal) -> Decimal:
        """Validate total_amount is positive."""
        if v <= 0:
            raise ValueError("total_amount must be positive")
        return v


class InvoiceCreate(InvoiceBase):
    """Schema for creating invoices."""

    @field_validator("due_date")
    @classmethod
    def due_date_must_be_after_invoice_date(cls, v: date, info) -> date:
        invoice_date = info.data.get("invoice_date")
        if invoice_date and v < invoice_date:
            raise ValueError("due_date must be after or equal to invoice_date")
        return v


class InvoiceUpdate(BaseModel):
    """Schema for updating invoices."""

    status: Optional[InvoiceStatus] = None
    total_amount_usd: Optional[Decimal] = None
    fx_rate: Optional[Decimal] = None
    stale_fx_rate: Optional[bool] = None
    ocr_completed_at: Optional[datetime] = None
    matching_completed_at: Optional[datetime] = None
    anomaly_completed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None


class InvoiceResponse(InvoiceBase):
    """Schema for invoice response."""

    invoice_id: UUID
    created_at: datetime
    updated_at: datetime
    line_items: Optional[List[InvoiceLineItemResponse]] = []

    model_config = ConfigDict(from_attributes=True)
