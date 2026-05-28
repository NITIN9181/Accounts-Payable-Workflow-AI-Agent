"""Audit logger service for AP Workflow Agent."""

from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from ap_workflow.database.session import get_session
from ap_workflow.models.audit_log import AuditLog, AuditAction, AuditEntityType, AuditActorType
from ap_workflow.models.invoice import Invoice
from ap_workflow.models.exception import InvoiceException
from ap_workflow.models.approval import Approval
from ap_workflow.models.payment import Payment


class AuditLoggerService:
    """Service for creating immutable audit logs."""

    def __init__(self, db: Session = None):
        """Initialize audit logger service with database session."""
        self.db = db or next(get_session())

    def mask_sensitive_fields(self, data: Any) -> Any:
        """Mask sensitive fields in nested data structures."""
        # Use exact-word or specific patterns so that "vendor_key", "monkey",
        # etc. are not falsely redacted.  Patterns are matched against the
        # lower-cased field name.
        sensitive_patterns = [
            "bank_account", "account_number", "ssn", "credit_card",
            "card_number", "routing_number", "password", "secret_key",
            "api_key", "private_key", "access_token", "refresh_token",
            "auth_token",
        ]

        if isinstance(data, list):
            return [self.mask_sensitive_fields(v) for v in data]

        if not isinstance(data, dict):
            return data

        masked: Dict[str, Any] = {}
        for key, value in data.items():
            key_lower = str(key).lower()
            if any(pattern in key_lower for pattern in sensitive_patterns):
                masked[key] = "***REDACTED***"
                continue
            masked[key] = self.mask_sensitive_fields(value)

        return masked

    def create_audit_log(
        self,
        actor_id,
        actor_type: AuditActorType,
        action_type: AuditAction,
        entity_type: AuditEntityType,
        entity_id,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Create audit log record."""
        # Mask sensitive fields (use `is not None` to preserve empty dicts)
        before_state_masked = self.mask_sensitive_fields(before_state) if before_state is not None else None
        after_state_masked = self.mask_sensitive_fields(after_state) if after_state is not None else None

        audit_log = AuditLog(
            actor_id=actor_id,
            actor_type=actor_type.value,
            action_type=action_type.value,
            entity_type=entity_type.value,
            entity_id=entity_id,
            before_state=before_state_masked,
            after_state=after_state_masked,
            ip_address=ip_address,
            user_agent=user_agent
        )

        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)

        return audit_log

    def log_invoice_created(self, invoice: Invoice) -> AuditLog:
        """Log invoice creation."""
        return self.create_audit_log(
            actor_id=None,
            actor_type=AuditActorType.SYSTEM,
            action_type=AuditAction.INVOICE_CREATED,
            entity_type=AuditEntityType.INVOICE,
            entity_id=invoice.invoice_id,
            after_state={
                "invoice_id": str(invoice.invoice_id),
                "vendor_key": invoice.vendor_key,
                "status": invoice.status.value
            }
        )

    def log_exception_created(self, exception: InvoiceException) -> AuditLog:
        """Log exception creation."""
        return self.create_audit_log(
            actor_id=None,
            actor_type=AuditActorType.SYSTEM,
            action_type=AuditAction.EXCEPTION_CREATED,
            entity_type=AuditEntityType.EXCEPTION,
            entity_id=exception.exception_id,
            after_state={
                "exception_id": str(exception.exception_id),
                "exception_type": exception.exception_type,
                "severity": float(exception.severity)
            }
        )

    def log_approval_created(self, approval: Approval) -> AuditLog:
        """Log approval creation."""
        return self.create_audit_log(
            actor_id=None,
            actor_type=AuditActorType.SYSTEM,
            action_type=AuditAction.APPROVAL_CREATED,
            entity_type=AuditEntityType.APPROVAL,
            entity_id=approval.approval_id,
            after_state={
                "approval_id": str(approval.approval_id),
                "approval_queue": approval.approval_queue,
                "status": approval.status.value
            }
        )

    def log_payment_scheduled(self, payment: Payment) -> AuditLog:
        """Log payment scheduling."""
        return self.create_audit_log(
            actor_id=None,
            actor_type=AuditActorType.SYSTEM,
            action_type=AuditAction.PAYMENT_SCHEDULED,
            entity_type=AuditEntityType.PAYMENT,
            entity_id=payment.payment_id,
            after_state={
                "payment_id": str(payment.payment_id),
                "scheduled_payment_date": str(payment.scheduled_payment_date),
                "payment_method": payment.payment_method
            }
        )

    def get_audit_logs_for_entity(
        self,
        entity_type: AuditEntityType,
        entity_id
    ) -> list[AuditLog]:
        """Get audit logs for entity, sorted by created_at ascending."""
        return self.db.query(AuditLog).filter(
            AuditLog.entity_type == entity_type.value,
            AuditLog.entity_id == entity_id
        ).order_by(AuditLog.created_at.asc()).all()
