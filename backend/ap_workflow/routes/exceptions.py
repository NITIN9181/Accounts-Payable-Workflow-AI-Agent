"""Exception API routes for AP Workflow Agent."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID

from ap_workflow.database.session import get_session
from ap_workflow.models.exception import InvoiceException, SeverityBand
from ap_workflow.schemas.exception import InvoiceExceptionResponse
from ap_workflow.services.llm_explainer import LLMExplainerService

router = APIRouter(prefix="/api/v1/exceptions", tags=["exceptions"])


@router.get("/", response_model=List[InvoiceExceptionResponse])
def list_exceptions(
    severity_band: Optional[SeverityBand] = None,
    resolved: Optional[bool] = None,
    db: Session = Depends(get_session)
):
    """List exceptions with filtering."""
    query = db.query(InvoiceException)

    if severity_band:
        query = query.filter(InvoiceException.severity_band == severity_band.value)

    if resolved is not None:
        query = query.filter(InvoiceException.resolved == resolved)

    return query.all()


@router.get("/{exception_id}", response_model=InvoiceExceptionResponse)
def get_exception(exception_id: UUID, db: Session = Depends(get_session)):
    """Get exception by ID."""
    exception = db.query(InvoiceException).filter(
        InvoiceException.exception_id == exception_id
    ).first()

    if not exception:
        raise HTTPException(status_code=404, detail="Exception not found")

    return exception


@router.put("/{exception_id}/resolve")
def resolve_exception(
    exception_id: UUID,
    notes: str = None,
    db: Session = Depends(get_session)
):
    """Resolve exception."""
    exception = db.query(InvoiceException).filter(
        InvoiceException.exception_id == exception_id
    ).first()

    if not exception:
        raise HTTPException(status_code=404, detail="Exception not found")

    exception.resolved = True
    exception.notes = notes
    db.commit()
    db.refresh(exception)

    return exception
