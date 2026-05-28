"""Approval Pydantic schemas for AP Workflow Agent."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict
from uuid import UUID

from ap_workflow.models.approval import ApprovalStatus, ApprovalQueue


class ApprovalBase(BaseModel):
    """Base approval schema."""

    invoice_id: UUID
    exception_id: Optional[UUID] = None
    approver_id: Optional[UUID] = None
    approver_role: Optional[str] = None
    approval_queue: Optional[str] = None
    status: Optional[str] = ApprovalStatus.PENDING
    sla_deadline: datetime
    sla_violated: Optional[bool] = False
    notes: Optional[str] = None


class ApprovalCreate(ApprovalBase):
    """Schema for creating approvals."""

    pass


class ApprovalResponse(ApprovalBase):
    """Schema for approval response."""

    approval_id: UUID
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
