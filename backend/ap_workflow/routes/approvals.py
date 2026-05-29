"""Approval management routes for AP Workflow Agent."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from ap_workflow.database.session import get_db
from ap_workflow.schemas.approval import ApprovalResponse, ApprovalCreate
from ap_workflow.services.approval_management import ApprovalManagementService
from ap_workflow.core.deps import get_current_claims

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])

# Dollar thresholds — keep in sync with frontend useRole.ts and settings defaults
_CLERK_THRESHOLD = 5_000
_MANAGER_THRESHOLD = 25_000


def _check_role_authority(role: str, amount: float, action: str) -> None:
    """Raise 403 if the role is not authorised to take this action on this amount."""
    if action not in ("APPROVED", "REJECTED", "ESCALATED", "HELD"):
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    # Escalate / Hold are always allowed for any role
    if action in ("ESCALATED", "HELD"):
        return

    if role == "AP_CLERK" and amount > _CLERK_THRESHOLD:
        raise HTTPException(
            status_code=403,
            detail=f"AP Clerk cannot approve invoices above ${_CLERK_THRESHOLD:,}. Please escalate.",
        )
    if role == "MANAGER" and amount > _MANAGER_THRESHOLD:
        raise HTTPException(
            status_code=403,
            detail=f"Manager cannot approve invoices above ${_MANAGER_THRESHOLD:,}. Please escalate to CFO.",
        )


@router.post("/{approval_id}/action", response_model=ApprovalResponse)
def handle_approval_action(
    approval_id: UUID,
    action: str = Query(..., description="Action: APPROVED, REJECTED, ESCALATED, or HELD"),
    approver_id: UUID = Query(..., description="ID of the approver"),
    approver_role: str = Query(..., description="Role of approver: AP_CLERK, MANAGER, or CFO"),
    notes: Optional[str] = Query(None, description="Optional notes from approver"),
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_claims),
) -> ApprovalResponse:
    """Handle approval action with role-based authority enforcement."""
    try:
        # Verify the role in the JWT matches what was sent
        jwt_role = claims.get("role", "")
        if jwt_role != approver_role:
            raise HTTPException(
                status_code=403,
                detail="approver_role does not match your authenticated role.",
            )

        service = ApprovalManagementService(db)
        approval = service.get_approval(approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail=f"Approval not found: {approval_id}")

        # Get the invoice amount for authority check
        invoice_amount = 0.0
        if approval.invoice:
            invoice_amount = float(approval.invoice.total_amount_usd or 0)

        # Enforce role authority
        _check_role_authority(approver_role, invoice_amount, action)

        approval = service.handle_approval_action(
            approval_id=approval_id,
            action=action,
            approver_id=approver_id,
            approver_role=approver_role,
            notes=notes,
        )
        return ApprovalResponse.from_orm(approval)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error handling approval action: {str(e)}")


@router.get("/queue/{queue_name}", response_model=dict)
def get_approval_queue(
    queue_name: str = Path(..., description="Queue name: AP_CLERK_QUEUE, MANAGER_QUEUE, or CFO_ESCALATION_QUEUE"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of records"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    severity: Optional[str] = Query(None, description="Filter by severity band: CRITICAL, HIGH, MEDIUM, LOW"),
    vendor_key: Optional[str] = Query(None, description="Filter by vendor_key"),
    db: Session = Depends(get_db),
) -> dict:
    """Get pending approvals from a specific queue, enriched with invoice data."""
    try:
        from ap_workflow.models.invoice import Invoice

        service = ApprovalManagementService(db)
        approvals, total_count = service.get_approval_queue(
            queue=queue_name,
            limit=limit,
            offset=offset,
            severity_filter=severity,
            vendor_filter=vendor_key,
        )

        # Enrich each approval with invoice fields the frontend needs
        enriched = []
        for a in approvals:
            invoice = db.query(Invoice).filter(Invoice.invoice_id == a.invoice_id).first()
            row = ApprovalResponse.from_orm(a).model_dump()
            if invoice:
                row["vendor_name"] = invoice.vendor_name
                row["invoice_number"] = invoice.invoice_number
                row["amount"] = float(invoice.total_amount_usd or invoice.total_amount or 0)
                row["due_date"] = str(invoice.due_date) if invoice.due_date else None
                row["invoice_id"] = str(invoice.invoice_id)
            else:
                row["vendor_name"] = "Unknown Vendor"
                row["invoice_number"] = "N/A"
                row["amount"] = 0
                row["due_date"] = None
            enriched.append(row)

        return {
            "approvals": enriched,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        import traceback
        print(f"Error retrieving approval queue: {e}")
        traceback.print_exc()
        # Return empty queue instead of 500 error
        return {
            "approvals": [],
            "total_count": 0,
            "limit": limit,
            "offset": offset,
            "error": str(e)
        }


@router.get("/{approval_id}", response_model=ApprovalResponse)
def get_approval(
    approval_id: UUID,
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    """Get approval record by ID.

    Args:
        approval_id: ID of the approval
        db: Database session

    Returns:
        Approval record

    Raises:
        HTTPException: If approval not found
    """
    try:
        service = ApprovalManagementService(db)
        approval = service.get_approval(approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail=f"Approval not found: {approval_id}")
        return ApprovalResponse.from_orm(approval)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving approval: {str(e)}")


@router.get("/invoice/{invoice_id}", response_model=List[ApprovalResponse])
def get_approvals_for_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
) -> List[ApprovalResponse]:
    """Get all approvals for an invoice.

    Args:
        invoice_id: ID of the invoice
        db: Database session

    Returns:
        List of approval records
    """
    try:
        service = ApprovalManagementService(db)
        approvals = service.get_approvals_for_invoice(invoice_id)
        return [ApprovalResponse.from_orm(a) for a in approvals]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving approvals: {str(e)}")


@router.post("/detect-sla-violations", response_model=dict)
def detect_sla_violations(
    db: Session = Depends(get_db),
) -> dict:
    """Detect and escalate approvals with SLA deadline violations.

    Args:
        db: Database session

    Returns:
        Dictionary with count of violations detected and escalated
    """
    try:
        service = ApprovalManagementService(db)
        violations = service.detect_sla_violations()
        return {
            "violations_detected": len(violations),
            "violations": [ApprovalResponse.from_orm(v) for v in violations],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error detecting SLA violations: {str(e)}")
