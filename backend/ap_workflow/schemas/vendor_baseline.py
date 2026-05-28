"""Vendor baseline Pydantic schemas for AP Workflow Agent."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID


class VendorBaselineBase(BaseModel):
    """Base vendor baseline schema."""

    vendor_key: str
    vendor_name: Optional[str] = None
    txn_count_total: Optional[int] = 0
    mean_invoice_amount_30d: Optional[Decimal] = None
    std_invoice_amount_30d: Optional[Decimal] = None
    p95_invoice_amount_90d: Optional[Decimal] = None
    avg_days_to_pay_90d: Optional[float] = None
    auto_approve_max_amount: Optional[Decimal] = None
    auto_approve_max_zscore: Optional[float] = Field(default=None, ge=1.5, le=4.0)
    preferred_payment_method: Optional[str] = None


class VendorBaselineCreate(VendorBaselineBase):
    """Schema for creating vendor baselines."""

    pass


class VendorBaselineResponse(VendorBaselineBase):
    """Schema for vendor baseline response."""

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
