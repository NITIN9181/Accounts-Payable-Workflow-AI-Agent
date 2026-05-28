"""Payment Pydantic schemas for AP Workflow Agent."""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict
from uuid import UUID

from ap_workflow.models.payment import PaymentMethod


class PaymentBase(BaseModel):
    """Base payment schema."""

    invoice_id: UUID
    scheduled_payment_date: date
    payment_method: Optional[str] = None
    payment_amount: Decimal
    discount_captured: Optional[Decimal] = None
    status: Optional[str] = "SCHEDULED"


class PaymentCreate(PaymentBase):
    """Schema for creating payments."""

    pass


class PaymentResponse(PaymentBase):
    """Schema for payment response."""

    payment_id: UUID
    created_at: datetime
    executed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PaymentBatchBase(BaseModel):
    """Base payment batch schema."""

    scheduled_payment_date: date
    total_outflow: Optional[Decimal] = None
    invoice_count: Optional[int] = None
    status: Optional[str] = "PENDING"


class PaymentBatchCreate(PaymentBatchBase):
    """Schema for creating payment batches."""

    pass


class PaymentBatchResponse(PaymentBatchBase):
    """Schema for payment batch response."""

    batch_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
