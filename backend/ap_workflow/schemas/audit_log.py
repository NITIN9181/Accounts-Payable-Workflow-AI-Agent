"""Audit log Pydantic schemas for AP Workflow Agent."""

from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, ConfigDict
from uuid import UUID

from ap_workflow.models.audit_log import AuditAction, AuditEntityType, AuditActorType


class AuditLogResponse(BaseModel):
    """Schema for audit log response."""

    log_id: UUID
    actor_id: Optional[UUID] = None
    actor_type: Optional[str] = None
    action_type: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
