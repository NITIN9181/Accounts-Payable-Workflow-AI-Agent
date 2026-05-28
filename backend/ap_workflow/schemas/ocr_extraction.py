"""OCR extraction Pydantic schemas for AP Workflow Agent."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from pydantic import BaseModel, ConfigDict, field_validator
from uuid import UUID


class OCRExtractionBase(BaseModel):
    """Base OCR extraction schema."""

    invoice_id: UUID
    invoice_number: Optional[str] = None
    invoice_number_confidence: Optional[Decimal] = None
    vendor_name: Optional[str] = None
    vendor_name_confidence: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    total_amount_confidence: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    tax_amount_confidence: Optional[Decimal] = None
    invoice_date: Optional[date] = None
    invoice_date_confidence: Optional[Decimal] = None
    due_date: Optional[date] = None
    due_date_confidence: Optional[Decimal] = None
    po_reference: Optional[str] = None
    po_reference_confidence: Optional[Decimal] = None
    ocr_raw_json: Optional[Dict[str, Any]] = None

    @field_validator(
        "invoice_number_confidence",
        "vendor_name_confidence",
        "total_amount_confidence",
        "tax_amount_confidence",
        "invoice_date_confidence",
        "due_date_confidence",
        "po_reference_confidence",
        mode="before"
    )
    @classmethod
    def validate_confidence_range(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate confidence scores are in range [0.0, 1.0]."""
        if v is not None and (v < 0 or v > 1):
            raise ValueError("Confidence score must be in range [0.0, 1.0]")
        return v


class OCRExtractionCreate(OCRExtractionBase):
    """Schema for creating OCR extractions."""

    pass


class OCRExtractionResponse(OCRExtractionBase):
    """Schema for OCR extraction response."""

    extraction_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
