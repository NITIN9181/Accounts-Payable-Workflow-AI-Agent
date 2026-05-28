"""Invoice API routes for AP Workflow Agent."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID

from ap_workflow.core.deps import get_current_claims
from ap_workflow.database.session import get_session
from ap_workflow.models.invoice import Invoice, InvoiceStatus
from ap_workflow.models.audit_log import AuditEntityType
from ap_workflow.schemas.audit_log import AuditLogResponse
from ap_workflow.schemas.invoice import InvoiceCreate, InvoiceResponse, InvoiceUpdate
from ap_workflow.services.ingestion import IngestionService
from ap_workflow.services.ocr import OCRService
from ap_workflow.services.audit_logger import AuditLoggerService

router = APIRouter(prefix="/api/v1/invoices", tags=["invoices"])


@router.post("/upload", response_model=InvoiceResponse)
async def upload_invoice(
    file: UploadFile = File(...),
    vendor_key: str = Form(...),
    vendor_name: str = Form(...),
    db: Session = Depends(get_session)
):
    """Upload invoice file and create invoice record."""
    # Read file content
    file_content = await file.read()

    # Process upload
    ingestion_service = IngestionService(db)
    invoice = ingestion_service.upload_invoice(
        file_content=file_content,
        vendor_key=vendor_key,
        vendor_name=vendor_name,
        ingestion_source="upload"
    )

    return invoice


@router.post("/webhook")
async def webhook_invoice(
    vendor_key: str,
    invoice_data: dict,
    signature: str = None,
    db: Session = Depends(get_session)
):
    """Process invoice from webhook."""
    # Validate signature (would use HMAC-SHA256)
    # For now, skip validation

    ingestion_service = IngestionService(db)
    invoice = ingestion_service.webhook_invoice(
        vendor_key=vendor_key,
        invoice_data=invoice_data,
        signature=signature or "",
        expected_signature=signature or ""
    )

    return invoice


@router.post("/manual", response_model=InvoiceResponse)
def manual_entry_invoice(
    vendor_name: str,
    invoice_number: str,
    total_amount: float,
    invoice_date: str,
    due_date: str,
    po_reference: Optional[str] = None,
    db: Session = Depends(get_session)
):
    """Process manually entered invoice."""
    ingestion_service = IngestionService(db)
    invoice = ingestion_service.manual_entry_invoice(
        vendor_name=vendor_name,
        invoice_number=invoice_number,
        total_amount=total_amount,
        invoice_date=invoice_date,
        due_date=due_date,
        po_reference=po_reference
    )

    return invoice


@router.get("/", response_model=List[InvoiceResponse])
def list_invoices(
    status: Optional[InvoiceStatus] = None,
    vendor_key: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_session)
):
    """List invoices with filtering."""
    query = db.query(Invoice)

    if status:
        query = query.filter(Invoice.status == status)

    if vendor_key:
        query = query.filter(Invoice.vendor_key == vendor_key)

    if start_date:
        query = query.filter(Invoice.received_at >= start_date)

    if end_date:
        query = query.filter(Invoice.received_at <= end_date)

    return query.all()


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(invoice_id: UUID, db: Session = Depends(get_session)):
    """Get invoice by ID."""
    ingestion_service = IngestionService(db)
    invoice = ingestion_service.get_invoice(invoice_id)

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return invoice


@router.put("/{invoice_id}/status")
def update_invoice_status(
    invoice_id: UUID,
    status: InvoiceUpdate,
    db: Session = Depends(get_session)
):
    """Update invoice status."""
    ingestion_service = IngestionService(db)
    invoice = ingestion_service.update_invoice_status(invoice_id, status.status)

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return invoice


@router.get("/{invoice_id}/audit", response_model=List[AuditLogResponse])
def get_invoice_audit_trail(
    invoice_id: UUID,
    db: Session = Depends(get_session),
    claims: dict = Depends(get_current_claims),
):
    """Retrieve audit trail for an invoice, sorted chronologically with masking + RBAC."""
    # Ensure invoice exists
    invoice = db.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    role = str(claims.get("role") or "")
    subject = claims.get("sub")
    subject_str = str(subject) if subject is not None else None

    audit_logger = AuditLoggerService(db)
    logs = audit_logger.get_audit_logs_for_entity(AuditEntityType.INVOICE, invoice_id)

    # RBAC rules (per spec; department scoping not implemented in data model)
    # - CFO/ADMIN: view all logs
    # - MANAGER: view all logs (no department dimension available)
    # - AP_CLERK: can view logs for their own actions only
    if role not in {"CFO", "ADMIN", "MANAGER"}:
        if not subject_str:
            raise HTTPException(status_code=403, detail="Insufficient permissions for audit trail")
        logs = [l for l in logs if (l.actor_id is not None and str(l.actor_id) == subject_str)]

    return logs
