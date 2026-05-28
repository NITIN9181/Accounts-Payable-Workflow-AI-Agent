"""Decision engine service for AP Workflow Agent."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from ap_workflow.database.session import get_session
from ap_workflow.models.invoice import Invoice, InvoiceStatus
from ap_workflow.models.exception import InvoiceException
from ap_workflow.models.approval import Approval, ApprovalStatus, ApprovalQueue
from ap_workflow.models.audit_log import AuditLog, AuditAction, AuditEntityType, AuditActorType
from ap_workflow.models.anomaly_detection import AnomalyDetection
from ap_workflow.models.vendor_baseline import VendorBaseline
from ap_workflow.core.config import settings
from ap_workflow.services import websocket_events


class DecisionEngine:
    """Service for making auto-approval decisions and routing exceptions."""

    def __init__(self, db: Session = None):
        """Initialize decision engine with database session."""
        self.db = db or next(get_session())
        self.default_auto_approve_max = settings.default_auto_approve_max_amount

    def get_auto_approve_threshold(self, vendor_key: str) -> Decimal:
        """Get auto-approve threshold for vendor."""
        baseline = self.db.query(VendorBaseline).filter(
            VendorBaseline.vendor_key == vendor_key
        ).first()

        if baseline and baseline.auto_approve_max_amount:
            return baseline.auto_approve_max_amount

        return Decimal(str(self.default_auto_approve_max))

    def get_severity_threshold(self, severity: Decimal) -> ApprovalQueue:
        """Determine approval queue based on severity."""
        if severity > Decimal("0.8"):
            return ApprovalQueue.CFO_ESCALATION_QUEUE
        elif severity >= Decimal("0.6"):
            return ApprovalQueue.MANAGER_QUEUE
        else:
            return ApprovalQueue.AP_CLERK_QUEUE

    def get_sla_hours(self, queue: ApprovalQueue) -> int:
        """Get SLA hours for queue."""
        if queue == ApprovalQueue.CFO_ESCALATION_QUEUE:
            return settings.cfo_sla_hours
        elif queue == ApprovalQueue.MANAGER_QUEUE:
            return settings.manager_sla_hours
        else:
            return settings.ap_clerk_sla_hours

    def determine_exception_priority(self, exceptions: list[InvoiceException]) -> Optional[InvoiceException]:
        """Determine highest priority exception."""
        priority_order = [
            "DUPLICATE_EXACT",
            "ANOMALY",
            "PO_MISMATCH",
            "PARTIAL_RECEIPT",
            "PO_MISSING",
            "RECEIPT_MISSING",
            "INCOMPLETE_DATA"
        ]

        if not exceptions:
            return None

        # Sort by priority
        sorted_exceptions = sorted(
            exceptions,
            key=lambda e: (
                priority_order.index(e.exception_type) if e.exception_type in priority_order else 999,
                -float(e.severity)
            )
        )

        return sorted_exceptions[0]

    def _should_auto_approve(self, invoice: Invoice, exceptions: list[InvoiceException], anomaly: Optional[AnomalyDetection]) -> bool:
        """Internal check for auto-approval eligibility."""
        auto_approve_threshold = self.get_auto_approve_threshold(invoice.vendor_key)
        
        return (
            len(exceptions) == 0 and
            invoice.total_amount_usd < auto_approve_threshold and
            (anomaly.final_severity if anomaly else 0) < 0.4
        )

    def process_invoice(self, invoice_id: str) -> Optional[Approval]:
        """Process invoice and make auto-approval decision."""
        invoice = self.db.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        # Get exceptions
        exceptions = self.db.query(InvoiceException).filter(
            InvoiceException.invoice_id == invoice_id,
            ~InvoiceException.resolved
        ).all()

        # Get anomaly detection
        anomaly = self.db.query(AnomalyDetection).filter(
            AnomalyDetection.invoice_id == invoice_id
        ).first()

        # Check auto-approval eligibility
        if self._should_auto_approve(invoice, exceptions, anomaly):
            # Auto-approve
            old_status = invoice.status
            invoice.status = InvoiceStatus.APPROVED
            invoice.approved_at = datetime.utcnow()
            self.db.commit()

            websocket_events.publish_invoice_status_changed(
                invoice_id,
                old_status.value,
                InvoiceStatus.APPROVED.value,
                actor_id="SYSTEM",
            )

            # Create audit log
            audit_log = AuditLog(
                actor_type=AuditActorType.SYSTEM,
                action_type=AuditAction.APPROVAL_ACTION_TAKEN,
                entity_type=AuditEntityType.INVOICE,
                entity_id=invoice_id,
                after_state={"status": InvoiceStatus.APPROVED.value}
            )
            self.db.add(audit_log)
            self.db.commit()

            return None

        # Route to approval queue
        if exceptions:
            # Get highest priority exception
            highest_priority = self.determine_exception_priority(exceptions)
            severity = highest_priority.severity if highest_priority else Decimal("0.0")
        else:
            severity = anomaly.final_severity if anomaly else Decimal("0.0")

        # Determine queue
        queue = self.get_severity_threshold(severity)
        sla_hours = self.get_sla_hours(queue)

        # Create approval record
        approval = Approval(
            invoice_id=invoice_id,
            approver_role="AP_CLERK",  # Default, would be assigned based on queue
            approval_queue=queue.value,
            status=ApprovalStatus.PENDING,
            sla_deadline=datetime.utcnow() + timedelta(hours=sla_hours)
        )

        self.db.add(approval)
        self.db.commit()
        self.db.refresh(approval)

        # Create audit log
        audit_log = AuditLog(
            actor_type=AuditActorType.SYSTEM,
            action_type=AuditAction.APPROVAL_CREATED,
            entity_type=AuditEntityType.INVOICE,
            entity_id=invoice_id,
            after_state={"approval_id": str(approval.approval_id), "queue": queue.value}
        )
        self.db.add(audit_log)
        self.db.commit()

        return approval
