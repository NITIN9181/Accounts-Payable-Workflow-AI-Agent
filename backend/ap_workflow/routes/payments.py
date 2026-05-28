"""Payment schedule routes for AP Workflow Agent."""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ap_workflow.database.session import get_db
from ap_workflow.models.invoice import Invoice, InvoiceStatus
from ap_workflow.models.payment import Payment, PaymentBatch
from ap_workflow.models.vendor_baseline import VendorBaseline

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@router.get("/schedule")
def get_payment_schedule(db: Session = Depends(get_db)) -> dict:
    """Get upcoming payment schedule grouped by date.

    Returns:
        Payment schedule with batches, discounts, alerts, and total outflow
    """
    try:
        today = datetime.utcnow().date()
        horizon = today + timedelta(days=30)

        # Get scheduled payments in the next 30 days
        payments = (
            db.query(Payment)
            .join(Invoice, Payment.invoice_id == Invoice.invoice_id)
            .join(VendorBaseline, Invoice.vendor_key == VendorBaseline.vendor_key, isouter=True)
            .filter(
                Payment.scheduled_payment_date >= today,
                Payment.scheduled_payment_date <= horizon,
                Payment.status.in_(["SCHEDULED", "PENDING"]),
            )
            .all()
        )

        # Group by date
        batches_by_date: dict[Any, list] = {}
        for p in payments:
            date_key = str(p.scheduled_payment_date)
            if date_key not in batches_by_date:
                batches_by_date[date_key] = []
            invoice = db.query(Invoice).filter(Invoice.invoice_id == p.invoice_id).first()
            batches_by_date[date_key].append({
                "invoice_id": str(p.invoice_id),
                "invoice_number": invoice.invoice_number if invoice else "N/A",
                "vendor_name": invoice.vendor_name if invoice else "Unknown",
                "amount": float(p.payment_amount or 0),
            })

        batches = [
            {
                "date": date,
                "total_amount": sum(inv["amount"] for inv in invoices),
                "invoices": invoices,
            }
            for date, invoices in sorted(batches_by_date.items())
        ]

        total_outflow = sum(b["total_amount"] for b in batches)

        # Discount opportunities: invoices with early payment terms expiring soon
        discounts = []
        upcoming_invoices = (
            db.query(Invoice)
            .filter(
                Invoice.status == InvoiceStatus.APPROVED,
                Invoice.due_date >= today,
                Invoice.due_date <= horizon,
            )
            .all()
        )
        for inv in upcoming_invoices:
            # Placeholder: real implementation would check payment terms
            pass

        # Risk alerts: payments exceeding $50k safety threshold on a single day
        alerts = []
        for batch in batches:
            if batch["total_amount"] > 50000:
                alerts.append({
                    "message": f"Payment batch on {batch['date']} exceeds safety threshold: ${batch['total_amount']:,.0f}"
                })

        return {
            "batches": batches,
            "discounts": discounts,
            "alerts": alerts,
            "total_outflow": total_outflow,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving payment schedule: {str(e)}")


@router.get("/cashflow-forecast")
def get_cashflow_forecast(db: Session = Depends(get_db)) -> list:
    """Get 30-day cash flow forecast.

    Returns:
        List of daily projected outflow amounts
    """
    try:
        today = datetime.utcnow().date()
        forecast = []

        for i in range(30):
            day = today + timedelta(days=i)
            total = (
                db.query(func.sum(Payment.payment_amount))
                .filter(
                    Payment.scheduled_payment_date == day,
                    Payment.status.in_(["SCHEDULED", "PENDING"]),
                )
                .scalar() or 0
            )
            forecast.append({
                "date": day.strftime("%b %d"),
                "amount": float(total),
                "threshold": 50000,
            })

        return forecast
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving cash flow forecast: {str(e)}")


@router.post("/capture-discount")
def capture_discount(body: dict, db: Session = Depends(get_db)) -> dict:
    """Capture early payment discount for an invoice.

    Args:
        body: Request body with invoiceId

    Returns:
        Success status
    """
    try:
        invoice_id = body.get("invoiceId")
        if not invoice_id:
            raise HTTPException(status_code=400, detail="invoiceId is required")

        payment = db.query(Payment).filter(Payment.invoice_id == invoice_id).first()
        if not payment:
            raise HTTPException(status_code=404, detail=f"Payment not found for invoice {invoice_id}")

        # Move payment date to today to capture discount
        payment.scheduled_payment_date = datetime.utcnow().date()
        db.commit()

        return {"status": "ok", "message": "Discount captured, payment rescheduled to today"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error capturing discount: {str(e)}")


@router.put("/reschedule")
def reschedule_payment(body: dict, db: Session = Depends(get_db)) -> dict:
    """Reschedule a payment to a new date.

    Args:
        body: Request body with invoiceId and newDate

    Returns:
        Success status
    """
    try:
        invoice_id = body.get("invoiceId")
        new_date_str = body.get("newDate")

        if not invoice_id or not new_date_str:
            raise HTTPException(status_code=400, detail="invoiceId and newDate are required")

        try:
            new_date = datetime.strptime(new_date_str, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="newDate must be in YYYY-MM-DD format")

        payment = db.query(Payment).filter(Payment.invoice_id == invoice_id).first()
        if not payment:
            raise HTTPException(status_code=404, detail=f"Payment not found for invoice {invoice_id}")

        payment.scheduled_payment_date = new_date
        db.commit()

        return {"status": "ok", "message": f"Payment rescheduled to {new_date_str}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rescheduling payment: {str(e)}")
