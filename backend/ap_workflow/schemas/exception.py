"""Exception Pydantic schemas for AP Workflow Agent."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from pydantic import BaseModel, ConfigDict, field_validator
from uuid import UUID

from ap_workflow.models.exception import SeverityBand


class InvoiceExceptionBase(BaseModel):
    """Base invoice exception schema."""

    invoice_id: UUID
    exception_type: Optional[str] = None
    severity: Decimal
    severity_band: Optional[str] = None
    details_json: Optional[str] = None
    llm_explanation: Optional[str] = None
    llm_explanation_fallback: Optional[bool] = False
    llm_explanation_ready: Optional[bool] = False
    resolved: Optional[bool] = False

    @field_validator("severity")
    @classmethod
    def validate_severity_range(cls, v: Decimal) -> Decimal:
        """Validate severity is in range [0.0, 1.0]."""
        if v < 0 or v > 1:
            raise ValueError("Severity must be in range [0.0, 1.0]")
        return v


class InvoiceExceptionCreate(InvoiceExceptionBase):
    """Schema for creating invoice exceptions."""

    pass


class InvoiceExceptionResponse(InvoiceExceptionBase):
    """Schema for invoice exception response."""

    exception_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
