"""Approval management service for AP Workflow Agent."""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ap_workflow.models.approval import Approval, ApprovalStatus, ApprovalQueue
from ap_workflow.models.invoice import Invoice, InvoiceStatus
from ap_workflow.models.audit_log import AuditLog, AuditAction, AuditEntityType, AuditActorType
from ap_workflow.services.audit_logger import AuditLoggerService


class ApprovalManagementService:
    """Service for managing invoice approvals and SLA tracking."""

    def __init__(self, db_session: Session):
        """Initialize approval management service.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db_session = db_session
        self.audit_logger = AuditLoggerService(db_session)

    def handle_approval_action(
        self,
        approval_id: UUID,
        action: str,
        approver_id: UUID,
        approver_role: str,
        notes: Optional[str] = None,
    ) -> Approval:
        """Handle approval action (APPROVED, REJECTED, ESCALATED).

        Args:
            approval_id: ID of the approval record
            action: Action to take (APPROVED, REJECTED, ESCALATED)
            approver_id: ID of the approver
            approver_role: Role of the approver (AP_CLERK, MANAGER, CFO)
            notes: Optional notes from approver

        Returns:
            Updated approval record

        Raises:
            ValueError: If action is invalid or approval not found
        """
        # Validate action
        valid_actions = [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.ESCALATED]
        if action not in [a.value for a in valid_actions]:
            raise ValueError(f"Invalid action: {action}. Must be one of {[a.value for a in valid_actions]}")

        # Get approval record
        approval = self.db_session.query(Approval).filter(Approval.approval_id == approval_id).first()
        if not approval:
            raise ValueError(f"Approval not found: {approval_id}")

        # Store before state for audit
        before_state = {
            "status": approval.status,
            "approver_id": str(approval.approver_id) if approval.approver_id else None,
            "completed_at": approval.completed_at.isoformat() if approval.completed_at else None,
        }

        # Update approval record
        approval.status = action
        approval.approver_id = approver_id
        approval.approver_role = approver_role
        approval.completed_at = datetime.utcnow()
        approval.notes = notes

        # Get associated invoice
        invoice = self.db_session.query(Invoice).filter(Invoice.invoice_id == approval.invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice not found: {approval.invoice_id}")

        # Update invoice status based on action
        if action == ApprovalStatus.APPROVED.value:
            invoice.status = InvoiceStatus.APPROVED
            # Trigger downstream workflow (payment scheduling)
            # This would typically publish to payment_queue
        elif action == ApprovalStatus.REJECTED.value:
            invoice.status = InvoiceStatus.REJECTED
            # Trigger hold workflow
        elif action == ApprovalStatus.ESCALATED.value:
            # Escalate to next higher queue
            self._escalate_to_next_queue(approval)

        # Store after state for audit
        after_state = {
            "status": approval.status,
            "approver_id": str(approval.approver_id),
            "completed_at": approval.completed_at.isoformat(),
        }

        # Create audit log
        self.audit_logger.create_audit_log(
            actor_id=approver_id,
            actor_type=AuditActorType.ANALYST,
            action_type=AuditAction.APPROVAL_ACTION_TAKEN,
            entity_type=AuditEntityType.APPROVAL,
            entity_id=approval_id,
            before_state=before_state,
            after_state=after_state,
        )

        # Commit changes
        self.db_session.commit()

        return approval

    def _escalate_to_next_queue(self, approval: Approval) -> None:
        """Escalate approval to next higher queue.

        Args:
            approval: Approval record to escalate
        """
        escalation_map = {
            ApprovalQueue.AP_CLERK_QUEUE.value: ApprovalQueue.MANAGER_QUEUE.value,
            ApprovalQueue.MANAGER_QUEUE.value: ApprovalQueue.CFO_ESCALATION_QUEUE.value,
            ApprovalQueue.CFO_ESCALATION_QUEUE.value: ApprovalQueue.CFO_ESCALATION_QUEUE.value,  # Already at top
        }

        current_queue = approval.approval_queue
        next_queue = escalation_map.get(current_queue, ApprovalQueue.CFO_ESCALATION_QUEUE.value)

        # Update queue
        approval.approval_queue = next_queue

        # Recalculate SLA deadline based on new queue
        sla_hours_map = {
            ApprovalQueue.AP_CLERK_QUEUE.value: 24,
            ApprovalQueue.MANAGER_QUEUE.value: 8,
            ApprovalQueue.CFO_ESCALATION_QUEUE.value: 2,
        }
        sla_hours = sla_hours_map.get(next_queue, 2)
        approval.sla_deadline = datetime.utcnow() + timedelta(hours=sla_hours)

    def detect_sla_violations(self) -> List[Approval]:
        """Detect approval records with SLA deadline violations.

        Returns:
            List of approvals with SLA violations
        """
        now = datetime.utcnow()

        # Find pending approvals past their SLA deadline
        violations = (
            self.db_session.query(Approval)
            .filter(
                Approval.status == ApprovalStatus.PENDING.value,
                Approval.sla_deadline < now,
                Approval.sla_violated == False,
            )
            .all()
        )

        # Mark as violated and escalate
        for approval in violations:
            approval.sla_violated = True
            self._escalate_to_next_queue(approval)

            # Create audit log for SLA violation
            self.audit_logger.create_audit_log(
                actor_id=None,
                actor_type=AuditActorType.SYSTEM,
                action_type=AuditAction.EXCEPTION_CREATED,
                entity_type=AuditEntityType.APPROVAL,
                entity_id=approval.approval_id,
                before_state={"sla_violated": False, "approval_queue": approval.approval_queue},
                after_state={"sla_violated": True, "approval_queue": approval.approval_queue},
            )

        self.db_session.commit()
        return violations

    def get_approval_queue(
        self,
        queue: str,
        limit: int = 50,
        offset: int = 0,
        severity_filter: Optional[str] = None,
        vendor_filter: Optional[str] = None,
    ) -> tuple[List[Approval], int]:
        """Get pending approvals from a specific queue with FIFO ordering.

        Args:
            queue: Approval queue (AP_CLERK_QUEUE, MANAGER_QUEUE, CFO_ESCALATION_QUEUE)
            limit: Maximum number of records to return
            offset: Offset for pagination
            severity_filter: Optional severity band filter (CRITICAL, HIGH, MEDIUM, LOW)
            vendor_filter: Optional vendor_key filter

        Returns:
            Tuple of (list of approvals, total count)
        """
        query = (
            self.db_session.query(Approval)
            .filter(
                Approval.approval_queue == queue,
                Approval.status == ApprovalStatus.PENDING.value,
            )
            .order_by(Approval.created_at.asc())  # FIFO ordering
        )

        # Apply severity filter if provided
        if severity_filter:
            from ap_workflow.models.exception import InvoiceException, SeverityBand

            query = query.join(InvoiceException).filter(InvoiceException.severity_band == severity_filter)

        # Apply vendor filter if provided
        if vendor_filter:
            from ap_workflow.models.invoice import Invoice

            query = query.join(Invoice).filter(Invoice.vendor_key == vendor_filter)

        # Get total count
        total_count = query.count()

        # Apply pagination
        approvals = query.limit(limit).offset(offset).all()

        return approvals, total_count

    def get_approval(self, approval_id: UUID) -> Optional[Approval]:
        """Get approval record by ID.

        Args:
            approval_id: ID of the approval

        Returns:
            Approval record or None if not found
        """
        return self.db_session.query(Approval).filter(Approval.approval_id == approval_id).first()

    def get_approvals_for_invoice(self, invoice_id: UUID) -> List[Approval]:
        """Get all approvals for an invoice.

        Args:
            invoice_id: ID of the invoice

        Returns:
            List of approval records
        """
        return (
            self.db_session.query(Approval)
            .filter(Approval.invoice_id == invoice_id)
            .order_by(Approval.created_at.desc())
            .all()
        )
