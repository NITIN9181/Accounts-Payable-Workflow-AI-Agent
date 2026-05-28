"""Vendor management routes for AP Workflow Agent."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ap_workflow.database.session import get_db
from ap_workflow.models.vendor_baseline import VendorBaseline
from ap_workflow.schemas.vendor_baseline import VendorBaselineResponse, VendorBaselineCreate
from ap_workflow.services.vendor_baseline import VendorBaselineService

router = APIRouter(prefix="/api/v1/vendors", tags=["vendors"])


@router.get("/baselines", response_model=list)
def list_vendor_baselines(
    db: Session = Depends(get_db),
) -> list:
    """List all vendor baselines.

    Returns:
        List of all vendor baseline records
    """
    try:
        baselines = db.query(VendorBaseline).all()
        return [VendorBaselineResponse.from_orm(b) for b in baselines]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving vendor baselines: {str(e)}")


@router.get("/{vendor_key}/baseline", response_model=VendorBaselineResponse)
def get_vendor_baseline(
    vendor_key: str,
    db: Session = Depends(get_db),
) -> VendorBaselineResponse:
    """Get vendor baseline configuration.

    Args:
        vendor_key: Unique vendor identifier
        db: Database session

    Returns:
        Vendor baseline record

    Raises:
        HTTPException: If vendor not found
    """
    try:
        service = VendorBaselineService(db)
        baseline = service.get_vendor_baseline(vendor_key)

        if not baseline:
            raise HTTPException(status_code=404, detail=f"Vendor not found: {vendor_key}")

        return VendorBaselineResponse.from_orm(baseline)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving vendor baseline: {str(e)}")


@router.put("/{vendor_key}/baseline", response_model=VendorBaselineResponse)
def update_vendor_baseline(
    vendor_key: str,
    baseline_data: VendorBaselineCreate,
    db: Session = Depends(get_db),
) -> VendorBaselineResponse:
    """Update vendor baseline configuration.

    Args:
        vendor_key: Unique vendor identifier
        baseline_data: Updated baseline configuration
        db: Database session

    Returns:
        Updated vendor baseline record

    Raises:
        HTTPException: If validation fails or vendor not found
    """
    try:
        service = VendorBaselineService(db)

        # Get existing baseline
        baseline = service.get_vendor_baseline(vendor_key)
        if not baseline:
            raise HTTPException(status_code=404, detail=f"Vendor not found: {vendor_key}")

        # Prepare updated values
        updated_auto_approve_max_amount = baseline_data.auto_approve_max_amount or baseline.auto_approve_max_amount
        updated_auto_approve_max_zscore = baseline_data.auto_approve_max_zscore or baseline.auto_approve_max_zscore

        # Validate configuration before updating
        is_valid, error_msg = service.validate_baseline_configuration(
            auto_approve_max_amount=updated_auto_approve_max_amount,
            auto_approve_max_zscore=updated_auto_approve_max_zscore,
            mean_invoice_amount_30d=baseline.mean_invoice_amount_30d
        )
        
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # Update fields
        if baseline_data.auto_approve_max_amount is not None:
            baseline.auto_approve_max_amount = baseline_data.auto_approve_max_amount

        if baseline_data.auto_approve_max_zscore is not None:
            baseline.auto_approve_max_zscore = baseline_data.auto_approve_max_zscore

        if baseline_data.payment_method is not None:
            baseline.payment_method = baseline_data.payment_method

        db.commit()
        return VendorBaselineResponse.from_orm(baseline)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating vendor baseline: {str(e)}")


@router.get("/{vendor_key}/analytics", response_model=dict)
def get_vendor_analytics(
    vendor_key: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db),
) -> dict:
    """Get vendor analytics and performance metrics.

    Args:
        vendor_key: Unique vendor identifier
        days: Number of days to analyze
        db: Database session

    Returns:
        Dictionary with vendor analytics

    Raises:
        HTTPException: If vendor not found
    """
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func

        from ap_workflow.models.invoice import Invoice, InvoiceStatus
        from ap_workflow.models.exception import InvoiceException, SeverityBand

        # Get vendor baseline
        service = VendorBaselineService(db)
        baseline = service.get_vendor_baseline(vendor_key)

        if not baseline:
            raise HTTPException(status_code=404, detail=f"Vendor not found: {vendor_key}")

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Get invoices for vendor
        invoices = (
            db.query(Invoice)
            .filter(Invoice.vendor_key == vendor_key, Invoice.created_at >= cutoff_date)
            .all()
        )

        # Calculate metrics
        total_invoices = len(invoices)
        total_amount = sum(inv.total_amount_usd or 0 for inv in invoices)
        approved_count = sum(1 for inv in invoices if inv.status == InvoiceStatus.APPROVED)
        rejected_count = sum(1 for inv in invoices if inv.status == InvoiceStatus.REJECTED)

        # Get exceptions
        exceptions = (
            db.query(InvoiceException)
            .join(Invoice)
            .filter(Invoice.vendor_key == vendor_key, InvoiceException.created_at >= cutoff_date)
            .all()
        )

        exception_count = len(exceptions)
        critical_count = sum(1 for exc in exceptions if exc.severity_band == SeverityBand.CRITICAL)
        high_count = sum(1 for exc in exceptions if exc.severity_band == SeverityBand.HIGH)

        # Calculate average days to pay
        paid_invoices = [inv for inv in invoices if inv.status == InvoiceStatus.PAID]
        avg_days_to_pay = (
            sum((inv.created_at - inv.created_at).days for inv in paid_invoices) / len(paid_invoices)
            if paid_invoices
            else 0
        )

        return {
            "vendor_key": vendor_key,
            "period_days": days,
            "total_invoices": total_invoices,
            "total_amount_usd": total_amount,
            "approved_count": approved_count,
            "rejected_count": rejected_count,
            "approval_rate": (approved_count / total_invoices * 100) if total_invoices > 0 else 0,
            "exception_count": exception_count,
            "critical_exceptions": critical_count,
            "high_exceptions": high_count,
            "exception_rate": (exception_count / total_invoices * 100) if total_invoices > 0 else 0,
            "avg_days_to_pay": avg_days_to_pay,
            "baseline": VendorBaselineResponse.from_orm(baseline),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving vendor analytics: {str(e)}")
