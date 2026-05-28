"""Payment scheduler service for AP Workflow Agent."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from ap_workflow.database.session import get_session
from ap_workflow.models.invoice import Invoice, InvoiceStatus
from ap_workflow.models.payment import Payment, PaymentMethod, PaymentBatch
from ap_workflow.models.audit_log import AuditLog, AuditAction, AuditEntityType, AuditActorType
from ap_workflow.models.vendor_baseline import VendorBaseline
from ap_workflow.core.config import settings
from ap_workflow.services.circuit_breaker import get_circuit_breaker
import logging

logger = logging.getLogger(__name__)


class PaymentSchedulerService:
    """Service for scheduling payments with discount optimization."""

    def __init__(self, db: Session = None):
        """Initialize payment scheduler service with database session."""
        self.db = db or next(get_session())

    def check_discount_availability(
        self,
        invoice: Invoice
    ) -> tuple[bool, Decimal, datetime]:
        """Check if early payment discount is available."""
        # This would check vendor payment terms
        # For now, return no discount
        return False, Decimal("0"), invoice.due_date

    def check_cash_balance_forecast(
        self,
        payment_amount: Decimal,
        payment_date
    ) -> bool:
        """Check if cash balance allows payment on date."""
        # This would check cash flow forecast
        # For now, return True
        return True

    def schedule_payment(self, invoice_id: str) -> Optional[Payment]:
        """Schedule payment for invoice with discount optimization."""
        invoice = self.db.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        # Check discount availability
        discount_available, discount_amount, discount_deadline = self.check_discount_availability(invoice)

        # Determine payment date
        if discount_available and discount_deadline > datetime.utcnow().date():
            # Check cash balance
            if self.check_cash_balance_forecast(invoice.total_amount_usd, discount_deadline):
                scheduled_payment_date = discount_deadline
                discount_captured = discount_amount
            else:
                scheduled_payment_date = invoice.due_date - timedelta(days=2)
                discount_captured = Decimal("0")
        else:
            scheduled_payment_date = invoice.due_date - timedelta(days=2)
            discount_captured = Decimal("0")

        # Get vendor baseline for payment method
        baseline = self.db.query(VendorBaseline).filter(
            VendorBaseline.vendor_key == invoice.vendor_key
        ).first()

        payment_method = baseline.preferred_payment_method if baseline else PaymentMethod.ACH

        # Create payment record
        payment = Payment(
            invoice_id=invoice_id,
            scheduled_payment_date=scheduled_payment_date,
            payment_method=payment_method,
            payment_amount=invoice.total_amount_usd or invoice.total_amount,
            discount_captured=discount_captured,
            status="SCHEDULED"
        )

        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)

        # Update invoice status
        invoice.status = InvoiceStatus.SCHEDULED
        self.db.commit()

        # Create audit log
        audit_log = AuditLog(
            actor_type=AuditActorType.SYSTEM,
            action_type=AuditAction.PAYMENT_SCHEDULED,
            entity_type=AuditEntityType.INVOICE,
            entity_id=invoice_id,
            after_state={
                "scheduled_payment_date": str(scheduled_payment_date),
                "payment_method": payment_method,
                "discount_captured": str(discount_captured)
            }
        )
        self.db.add(audit_log)
        self.db.commit()

        return payment

    def aggregate_payment_batch(self, payment_date) -> Optional[PaymentBatch]:
        """Aggregate payments for date into batch."""
        # Get payments for date
        payments = self.db.query(Payment).filter(
            Payment.scheduled_payment_date == payment_date,
            Payment.status == "SCHEDULED"
        ).all()

        if not payments:
            return None

        # Calculate total outflow
        total_outflow = sum(p.payment_amount for p in payments)

        # Create batch
        batch = PaymentBatch(
            scheduled_payment_date=payment_date,
            total_outflow=total_outflow,
            invoice_count=len(payments),
            status="PENDING"
        )

        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        return batch

    def get_payment(self, payment_id: str) -> Optional[Payment]:
        """Get payment by ID."""
        return self.db.query(Payment).filter(Payment.payment_id == payment_id).first()

    def execute_payment(self, payment_id: str) -> bool:
        """Execute payment via external processor with circuit breaker."""
        payment = self.get_payment(payment_id)
        if not payment:
            raise ValueError(f"Payment {payment_id} not found")

        def _payment_call():
            # In production, this would call the Payment Processor API
            # Simulate payment execution
            return True

        cb = get_circuit_breaker("payment_processor")
        try:
            success = cb(_payment_call)()
            if success:
                payment.status = "EXECUTED"
                self.db.commit()
                return True
        except Exception as e:
            logger.error(f"Circuit breaker triggered for Payment Processor: {e}")
            # Payment remains SCHEDULED, will be retried in next cycle
            return False

        return False
