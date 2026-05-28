"""Ingestion service for AP Workflow Agent."""

import hashlib
import uuid
from datetime import datetime
from typing import Optional
from io import BytesIO

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ap_workflow.database.session import get_session
from ap_workflow.models.invoice import Invoice, InvoiceStatus, InvoiceLineItem
from ap_workflow.models.audit_log import AuditLog, AuditAction, AuditEntityType, AuditActorType
from ap_workflow.services import websocket_events
from ap_workflow.schemas.invoice import InvoiceCreate


class IngestionService:
    """Service for handling invoice ingestion from multiple channels."""

    def __init__(self, db: Session = None):
        """Initialize ingestion service with database session."""
        self.db = db or next(get_session())

    def _compute_file_hash(self, file_content: bytes) -> str:
        """Compute SHA-256 hash of file content."""
        return hashlib.sha256(file_content).hexdigest()

    def _check_duplicate_file(self, file_hash: str, window_hours: int = 24) -> Optional[str]:
        """Check if file hash exists within time window."""
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        existing = self.db.query(Invoice).filter(
            Invoice.file_hash == file_hash,
            Invoice.received_at >= cutoff
        ).first()

        return existing.invoice_id if existing else None

    def upload_invoice(
        self,
        file_content: bytes,
        vendor_key: str,
        vendor_name: str,
        ingestion_source: str = "upload"
    ) -> Invoice:
        """Upload invoice file and create invoice record."""
        # Compute file hash
        file_hash = self._compute_file_hash(file_content)

        # Check for duplicate
        existing_id = self._check_duplicate_file(file_hash)
        if existing_id:
            raise ValueError(f"DUPLICATE_FILE_DETECTED: Original invoice_id={existing_id}")

        # Create invoice record
        invoice = Invoice(
            vendor_key=vendor_key,
            vendor_name=vendor_name,
            invoice_number="",  # Will be populated by OCR
            total_amount=0.0,  # Will be populated by OCR
            file_hash=file_hash,
            ingestion_source=ingestion_source,
            status=InvoiceStatus.PENDING_OCR,
            received_at=datetime.utcnow()
        )

        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)

        # Create audit log
        audit_log = AuditLog(
            actor_type=AuditActorType.SYSTEM,
            action_type=AuditAction.INVOICE_CREATED,
            entity_type=AuditEntityType.INVOICE,
            entity_id=invoice.invoice_id,
            after_state={"invoice_id": str(invoice.invoice_id), "status": invoice.status.value}
        )
        self.db.add(audit_log)
        self.db.commit()

        return invoice

    def webhook_invoice(
        self,
        vendor_key: str,
        invoice_data: dict,
        signature: str,
        expected_signature: str
    ) -> Invoice:
        """Process invoice from webhook with signature validation."""
        # Validate signature (HMAC-SHA256)
        if signature != expected_signature:
            raise ValueError("Invalid webhook signature")

        # Create invoice record
        invoice = Invoice(
            vendor_key=vendor_key,
            vendor_name=invoice_data.get("vendor_name", ""),
            invoice_number=invoice_data.get("invoice_number", ""),
            total_amount=invoice_data.get("total_amount", 0.0),
            invoice_date=invoice_data.get("invoice_date"),
            due_date=invoice_data.get("due_date"),
            po_reference=invoice_data.get("po_reference"),
            currency_code=invoice_data.get("currency_code", "USD"),
            ingestion_source="webhook",
            status=InvoiceStatus.PENDING_OCR,
            received_at=datetime.utcnow()
        )

        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)

        return invoice

    def manual_entry_invoice(
        self,
        vendor_name: str,
        invoice_number: str,
        total_amount: float,
        invoice_date: str,
        due_date: str,
        po_reference: Optional[str] = None
    ) -> Invoice:
        """Process manually entered invoice."""
        from datetime import datetime as dt

        invoice = Invoice(
            vendor_key=f"MANUAL_{uuid.uuid4().hex[:8]}",
            vendor_name=vendor_name,
            invoice_number=invoice_number,
            total_amount=total_amount,
            invoice_date=dt.fromisoformat(invoice_date).date(),
            due_date=dt.fromisoformat(due_date).date(),
            po_reference=po_reference,
            ingestion_source="manual",
            status=InvoiceStatus.PENDING_OCR,
            received_at=datetime.utcnow()
        )

        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)

        return invoice

    def get_invoice(self, invoice_id: uuid.UUID) -> Optional[Invoice]:
        """Get invoice by ID."""
        return self.db.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()

    def update_invoice_status(self, invoice_id: uuid.UUID, status: InvoiceStatus) -> Optional[Invoice]:
        """Update invoice status."""
        invoice = self.get_invoice(invoice_id)
        if invoice:
            old_status = invoice.status
            invoice.status = status
            self.db.commit()
            self.db.refresh(invoice)

            # Create audit log for status change
            audit_log = AuditLog(
                actor_type=AuditActorType.SYSTEM,
                action_type=AuditAction.INVOICE_STATUS_CHANGED,
                entity_type=AuditEntityType.INVOICE,
                entity_id=invoice_id,
                before_state={"status": old_status.value},
                after_state={"status": status.value}
            )
            self.db.add(audit_log)
            self.db.commit()

            websocket_events.publish_invoice_status_changed(
                invoice_id,
                old_status.value,
                status.value,
                actor_id="SYSTEM",
            )

        return invoice
