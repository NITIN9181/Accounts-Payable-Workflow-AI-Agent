"""LLM explainer service for AP Workflow Agent."""

import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from ap_workflow.database.session import get_session
from ap_workflow.models.exception import InvoiceException
from ap_workflow.models.llm_explanation import LLMExplanationCache, LLMRequest
from ap_workflow.models.audit_log import AuditLog, AuditAction, AuditEntityType, AuditActorType
from ap_workflow.core.config import settings
from ap_workflow.services import websocket_events
from ap_workflow.services.circuit_breaker import get_circuit_breaker
import requests
import logging

logger = logging.getLogger(__name__)


class LLMExplainerService:
    """Service for generating LLM explanations for exceptions."""

    def __init__(self, db: Session = None):
        """Initialize LLM explainer service with database session."""
        self.db = db or next(get_session())
        self.rate_limit_rpm = settings.llm_rate_limit_rpm
        self.queue_max_size = settings.llm_queue_max_size
        self.cache_ttl_days = 30

    def compute_cache_key(
        self,
        vendor_key: str,
        exception_type: str,
        exception_details: str
    ) -> str:
        """Compute cache key for LLM explanation."""
        hash_input = f"{vendor_key}{exception_type}{exception_details}"
        return hashlib.sha256(hash_input.encode()).hexdigest()

    def get_cached_explanation(self, cache_key: str) -> Optional[str]:
        """Get cached explanation if available."""
        cache_entry = self.db.query(LLMExplanationCache).filter(
            LLMExplanationCache.cache_key == cache_key,
            LLMExplanationCache.ttl_expires_at > datetime.utcnow()
        ).first()

        if cache_entry:
            # Update last accessed time
            cache_entry.last_accessed_at = datetime.utcnow()
            self.db.commit()
            return cache_entry.explanation

        return None

    def generate_fallback_explanation(
        self,
        vendor_name: str,
        total_amount: Decimal,
        invoice_date,
        mean_amount_30d: Decimal,
        exception_type: str
    ) -> str:
        """Generate template-based fallback explanation."""
        deviation = "above" if total_amount > mean_amount_30d else "below"
        return (
            f"{vendor_name} invoiced ${total_amount} on {invoice_date}, "
            f"which is {deviation} the 30-day average of ${mean_amount_30d}. "
            f"Exception type: {exception_type}."
        )

    def generate_explanation(
        self,
        exception_id: str,
        vendor_key: str,
        exception_type: str,
        exception_details: str,
        vendor_name: str,
        total_amount: Decimal,
        invoice_date,
        mean_amount_30d: Decimal
    ) -> tuple[Optional[str], bool]:
        """Generate explanation using LLM or fallback."""
        # Compute cache key
        cache_key = self.compute_cache_key(vendor_key, exception_type, exception_details)

        # Check cache
        cached = self.get_cached_explanation(cache_key)
        if cached:
            return cached, False

        # Generate fallback explanation
        explanation = self.generate_fallback_explanation(
            vendor_name,
            total_amount,
            invoice_date,
            mean_amount_30d,
            exception_type
        )

        # Store in cache
        cache_entry = LLMExplanationCache(
            cache_key=cache_key,
            vendor_key=vendor_key,
            exception_type=exception_type,
            explanation=explanation,
            fallback=True,
            ttl_expires_at=datetime.utcnow() + timedelta(days=self.cache_ttl_days)
        )
        self.db.add(cache_entry)
        self.db.commit()

        return explanation, True

    def update_exception_with_explanation(
        self,
        exception_id: str,
        explanation: str,
        is_fallback: bool
    ) -> Optional[InvoiceException]:
        """Update exception with generated explanation."""
        exception = self.db.query(InvoiceException).filter(
            InvoiceException.exception_id == exception_id
        ).first()

        if exception:
            exception.llm_explanation = explanation
            exception.llm_explanation_fallback = is_fallback
            exception.llm_explanation_ready = True
            self.db.commit()
            self.db.refresh(exception)

            # Create audit log
            audit_log = AuditLog(
                actor_type=AuditActorType.SYSTEM,
                action_type=AuditAction.EXCEPTION_RESOLVED,
                entity_type=AuditEntityType.EXCEPTION,
                entity_id=exception_id,
                after_state={"llm_explanation_ready": True}
            )
            self.db.add(audit_log)
            self.db.commit()

            websocket_events.publish_explanation_ready(exception)

        return exception

    def process_exception(self, exception_id: str) -> Optional[InvoiceException]:
        """Process exception and generate explanation with circuit breaker."""
        exception = self.db.query(InvoiceException).filter(
            InvoiceException.exception_id == exception_id
        ).first()

        if not exception:
            raise ValueError(f"Exception {exception_id} not found")

        # Get invoice details
        invoice = self.db.query(InvoiceException).filter(
            InvoiceException.exception_id == exception_id
        ).first()

        # Define the actual LLM call to be wrapped by the circuit breaker
        def _llm_call():
            # In a real implementation, this would call NVIDIA NIM API
            # For now, we simulate the call and return a generated explanation
            # This is where the actual requests.post would go
            return self.generate_explanation(
                exception_id=exception_id,
                vendor_key=invoice.vendor_key,
                exception_type=exception.exception_type,
                exception_details=exception.details_json or "",
                vendor_name=invoice.vendor_name,
                total_amount=invoice.total_amount_usd or invoice.total_amount,
                invoice_date=invoice.invoice_date,
                mean_amount_30d=Decimal("0")
            )

        # Wrap the LLM call with the NVIDIA NIM circuit breaker
        cb = get_circuit_breaker("nvidia_nim")
        try:
            explanation, is_fallback = cb(_llm_call)()
        except Exception as e:
            logger.error(f"Circuit breaker triggered for NVIDIA NIM: {e}")
            # Fallback to template-based explanation
            explanation, is_fallback = self.generate_explanation(
                exception_id=exception_id,
                vendor_key=invoice.vendor_key,
                exception_type=exception.exception_type,
                exception_details=exception.details_json or "",
                vendor_name=invoice.vendor_name,
                total_amount=invoice.total_amount_usd or invoice.total_amount,
                invoice_date=invoice.invoice_date,
                mean_amount_30d=Decimal("0")
            )

        # Update exception
        return self.update_exception_with_explanation(exception_id, explanation, is_fallback)
