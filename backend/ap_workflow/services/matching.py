"""Matching service for AP Workflow Agent."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session
from sqlalchemy import func

from ap_workflow.database.session import get_session
from ap_workflow.models.invoice import Invoice, InvoiceStatus
from ap_workflow.models.matching import PurchaseOrder, POLineItem, Receipt, ReceiptLineItem, MatchingResult
from ap_workflow.models.audit_log import AuditLog, AuditAction, AuditEntityType, AuditActorType
from ap_workflow.models.exception import InvoiceException, SeverityBand
from ap_workflow.core.config import settings


class MatchingService:
    """Service for three-way matching (PO → Receipt → Invoice)."""

    def __init__(self, db: Session = None):
        """Initialize matching service with database session."""
        self.db = db or next(get_session())

    def find_po(
        self,
        vendor_key: str,
        po_reference: Optional[str] = None,
        invoice_number: Optional[str] = None
    ) -> Optional[PurchaseOrder]:
        """Find matching PO by exact or fuzzy match."""
        # Try exact match first
        if po_reference:
            po = self.db.query(PurchaseOrder).filter(
                PurchaseOrder.vendor_key == vendor_key,
                PurchaseOrder.po_number == po_reference,
                PurchaseOrder.status.in_(['OPEN', 'PARTIALLY_RECEIVED'])
            ).first()
            if po:
                return po

        # Try fuzzy match
        if invoice_number:
            # This would use rapidfuzz for fuzzy matching
            # For now, return None
            pass

        return None

    def match_line_items(
        self,
        invoice_id: str,
        po_id: str
    ) -> tuple[bool, Optional[Dict[str, Any]]]:
        """Match invoice line items against PO line items."""
        # This would compare line items with tolerance
        # For now, return success
        return True, None

    def verify_receipt(
        self,
        po_id: str,
        invoice_id: str
    ) -> tuple[bool, Optional[Dict[str, Any]]]:
        """Verify receipt quantities match invoiced quantities."""
        # This would compare receipt quantities
        # For now, return success
        return True, None

    def _classify_match_result(self, match_status: str, variance_details: Optional[Dict[str, Any]]) -> tuple[str, Optional[Dict[str, Any]]]:
        """Internal match classification logic."""
        return match_status, variance_details

    def perform_three_way_match(self, invoice_id: str) -> MatchingResult:
        """Perform three-way match for invoice."""
        # Get invoice
        invoice = self.db.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        # Find PO
        po = self.find_po(invoice.vendor_key, invoice.po_reference, invoice.invoice_number)

        # Determine match status
        if not po:
            match_status = "PO_MISSING"
            variance_details = {"reason": "No matching PO found"}
        else:
            # Match line items
            line_items_match, line_item_variance = self.match_line_items(invoice_id, po.po_id)

            if not line_items_match:
                match_status = "PO_MISMATCH"
                variance_details = line_item_variance
            else:
                # Verify receipt
                receipt_match, receipt_variance = self.verify_receipt(po.po_id, invoice_id)

                if not receipt_match:
                    match_status = "PARTIAL_RECEIPT"
                    variance_details = receipt_variance
                else:
                    match_status = "PO_MATCHED"
                    variance_details = None

        # Classify result
        final_status, final_variance = self._classify_match_result(match_status, variance_details)

        # Create matching result
        matching_result = MatchingResult(
            invoice_id=invoice_id,
            po_id=po.po_id if po else None,
            match_status=final_status,
            variance_details=final_variance
        )

        self.db.add(matching_result)
        self.db.commit()
        self.db.refresh(matching_result)

        # Update invoice status
        invoice.matching_completed_at = datetime.utcnow()
        self.db.commit()

        # Create audit log
        audit_log = AuditLog(
            actor_type=AuditActorType.SYSTEM,
            action_type=AuditAction.THREE_WAY_MATCH_PERFORMED,
            entity_type=AuditEntityType.INVOICE,
            entity_id=invoice_id,
            after_state={"match_status": final_status}
        )
        self.db.add(audit_log)
        self.db.commit()

        return matching_result

    def get_matching_result(self, invoice_id: str) -> Optional[MatchingResult]:
        """Get matching result for invoice."""
        return self.db.query(MatchingResult).filter(
            MatchingResult.invoice_id == invoice_id
        ).first()
