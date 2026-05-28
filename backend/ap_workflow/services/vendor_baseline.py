"""Vendor baseline service for AP Workflow Agent."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func

from ap_workflow.database.session import get_session
from ap_workflow.models.invoice import Invoice, InvoiceStatus
from ap_workflow.models.vendor_baseline import VendorBaseline
from ap_workflow.models.vendor_baseline_history import VendorBaselineHistory
from ap_workflow.models.audit_log import AuditLog, AuditAction, AuditEntityType, AuditActorType
from ap_workflow.core.config import settings


class BaselineValidationError(Exception):
    """Exception raised when baseline configuration validation fails."""
    pass


class VendorBaselineService:
    """Service for maintaining vendor baseline statistics."""

    def __init__(self, db: Session = None):
        """Initialize vendor baseline service with database session."""
        self.db = db or next(get_session())

    def update_vendor_baseline(self, vendor_key: str) -> Optional[VendorBaseline]:
        """Update vendor baseline statistics with multi-currency normalization."""
        # Get paid invoices in past 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        ninety_days_ago = datetime.utcnow() - timedelta(days=90)

        # Get all paid invoices for vendor
        paid_invoices = self.db.query(Invoice).filter(
            Invoice.vendor_key == vendor_key,
            Invoice.status == InvoiceStatus.PAID
        ).all()

        # Count total transactions
        txn_count_total = len(paid_invoices)

        # Get paid invoices in past 30 days
        paid_30d = [i for i in paid_invoices if i.paid_at and i.paid_at >= thirty_days_ago]

        # Calculate mean and std for 30-day window using USD-normalized amounts
        if len(paid_30d) >= 2:
            # Normalize all amounts to USD using fx_rate
            amounts_usd = []
            for invoice in paid_30d:
                # Use total_amount_usd if available, otherwise calculate from total_amount * fx_rate
                if invoice.total_amount_usd:
                    amount_usd = float(invoice.total_amount_usd)
                elif invoice.fx_rate:
                    amount_usd = float(invoice.total_amount) * float(invoice.fx_rate)
                else:
                    # Fallback to total_amount if no FX rate (assume USD)
                    amount_usd = float(invoice.total_amount)
                amounts_usd.append(amount_usd)
            
            mean_30d = sum(amounts_usd) / len(amounts_usd)
            variance = sum((x - mean_30d) ** 2 for x in amounts_usd) / len(amounts_usd)
            std_30d = variance ** 0.5
        else:
            mean_30d = 0.0
            std_30d = 0.0

        # Get paid invoices in past 90 days
        paid_90d = [i for i in paid_invoices if i.paid_at and i.paid_at >= ninety_days_ago]

        # Calculate p95 for 90-day window using USD-normalized amounts
        if paid_90d:
            # Normalize all amounts to USD using fx_rate
            amounts_90d_usd = []
            for invoice in paid_90d:
                # Use total_amount_usd if available, otherwise calculate from total_amount * fx_rate
                if invoice.total_amount_usd:
                    amount_usd = float(invoice.total_amount_usd)
                elif invoice.fx_rate:
                    amount_usd = float(invoice.total_amount) * float(invoice.fx_rate)
                else:
                    # Fallback to total_amount if no FX rate (assume USD)
                    amount_usd = float(invoice.total_amount)
                amounts_90d_usd.append(amount_usd)
            
            amounts_90d = sorted(amounts_90d_usd)
            p95_index = int(len(amounts_90d) * 0.95)
            p95_90d = amounts_90d[min(p95_index, len(amounts_90d) - 1)]
        else:
            p95_90d = 0.0

        # Calculate average days to pay for 90-day window
        if paid_90d:
            days_to_pay = []
            for invoice in paid_90d:
                if invoice.paid_at and invoice.invoice_date:
                    days = (invoice.paid_at - invoice.invoice_date).days
                    days_to_pay.append(days)
            avg_days_to_pay = sum(days_to_pay) / len(days_to_pay) if days_to_pay else 0
        else:
            avg_days_to_pay = 0

        # Get or create vendor baseline
        baseline = self.db.query(VendorBaseline).filter(
            VendorBaseline.vendor_key == vendor_key
        ).first()

        if not baseline:
            baseline = VendorBaseline(vendor_key=vendor_key)

        # Update baseline
        baseline.txn_count_total = txn_count_total
        baseline.mean_invoice_amount_30d = Decimal(str(mean_30d))
        baseline.std_invoice_amount_30d = Decimal(str(std_30d))
        baseline.p95_invoice_amount_90d = Decimal(str(p95_90d))
        baseline.avg_days_to_pay_90d = avg_days_to_pay

        # Validate auto_approve_max_amount
        if baseline.auto_approve_max_amount:
            max_allowed = mean_30d * 10
            if baseline.auto_approve_max_amount > Decimal(str(max_allowed)):
                baseline.auto_approve_max_amount = Decimal(str(max_allowed))

        # Validate auto_approve_max_zscore
        if baseline.auto_approve_max_zscore:
            baseline.auto_approve_max_zscore = max(
                1.5,
                min(4.0, baseline.auto_approve_max_zscore)
            )

        self.db.add(baseline)
        self.db.commit()
        self.db.refresh(baseline)

        # Create historical snapshot
        history_snapshot = VendorBaselineHistory(
            vendor_key=vendor_key,
            mean_invoice_amount_30d=baseline.mean_invoice_amount_30d,
            std_invoice_amount_30d=baseline.std_invoice_amount_30d,
            p95_invoice_amount_90d=baseline.p95_invoice_amount_90d,
            avg_days_to_pay_90d=baseline.avg_days_to_pay_90d,
            txn_count_total=baseline.txn_count_total,
            auto_approve_max_amount=baseline.auto_approve_max_amount,
            auto_approve_max_zscore=baseline.auto_approve_max_zscore
        )
        self.db.add(history_snapshot)

        # Create audit log
        audit_log = AuditLog(
            actor_type=AuditActorType.SYSTEM,
            action_type=AuditAction.VENDOR_BASELINE_UPDATED,
            entity_type=AuditEntityType.VENDOR_BASELINE,
            entity_id=vendor_key,
            after_state={
                "mean_invoice_amount_30d": str(mean_30d),
                "std_invoice_amount_30d": str(std_30d),
                "txn_count_total": txn_count_total
            }
        )
        self.db.add(audit_log)
        self.db.commit()

        return baseline

    def get_vendor_baseline(self, vendor_key: str) -> Optional[VendorBaseline]:
        """Get vendor baseline by key."""
        return self.db.query(VendorBaseline).filter(
            VendorBaseline.vendor_key == vendor_key
        ).first()

    def update_baseline_on_payment(self, invoice_id: str) -> Optional[VendorBaseline]:
        """Update vendor baseline when invoice is paid."""
        invoice = self.db.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        return self.update_vendor_baseline(invoice.vendor_key)

    def validate_auto_approve_max_amount(
        self, 
        auto_approve_max_amount: Decimal, 
        mean_invoice_amount_30d: Decimal
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate auto_approve_max_amount configuration.
        
        Requirements:
        - auto_approve_max_amount >= 0
        - auto_approve_max_amount <= 10x mean_invoice_amount_30d
        
        Args:
            auto_approve_max_amount: The maximum amount for auto-approval
            mean_invoice_amount_30d: The mean invoice amount for the past 30 days
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if auto_approve_max_amount is None:
            return True, None
            
        # Check if non-negative
        if auto_approve_max_amount < 0:
            return False, "auto_approve_max_amount must be >= 0"
        
        # Check if within 10x mean
        if mean_invoice_amount_30d is not None and mean_invoice_amount_30d > 0:
            max_allowed = mean_invoice_amount_30d * 10
            if auto_approve_max_amount > max_allowed:
                return False, f"auto_approve_max_amount must be <= 10x mean_invoice_amount_30d (max: {max_allowed})"
        
        return True, None

    def validate_auto_approve_max_zscore(
        self, 
        auto_approve_max_zscore: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate auto_approve_max_zscore configuration.
        
        Requirements:
        - auto_approve_max_zscore must be in range [1.5, 4.0]
        
        Args:
            auto_approve_max_zscore: The maximum z-score for auto-approval
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if auto_approve_max_zscore is None:
            return True, None
            
        # Check if in valid range
        if auto_approve_max_zscore < 1.5:
            return False, "auto_approve_max_zscore must be >= 1.5"
        
        if auto_approve_max_zscore > 4.0:
            return False, "auto_approve_max_zscore must be <= 4.0"
        
        return True, None

    def validate_baseline_configuration(
        self,
        auto_approve_max_amount: Optional[Decimal] = None,
        auto_approve_max_zscore: Optional[float] = None,
        mean_invoice_amount_30d: Optional[Decimal] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate complete baseline configuration.
        
        Args:
            auto_approve_max_amount: The maximum amount for auto-approval
            auto_approve_max_zscore: The maximum z-score for auto-approval
            mean_invoice_amount_30d: The mean invoice amount for the past 30 days
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate auto_approve_max_amount
        if auto_approve_max_amount is not None:
            is_valid, error_msg = self.validate_auto_approve_max_amount(
                auto_approve_max_amount, 
                mean_invoice_amount_30d
            )
            if not is_valid:
                return False, error_msg
        
        # Validate auto_approve_max_zscore
        if auto_approve_max_zscore is not None:
            is_valid, error_msg = self.validate_auto_approve_max_zscore(auto_approve_max_zscore)
            if not is_valid:
                return False, error_msg
        
        return True, None
