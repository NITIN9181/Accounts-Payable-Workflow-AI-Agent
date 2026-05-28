"""Duplicate detection service for AP Workflow Agent."""

import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import func

from ap_workflow.database.session import get_session
from ap_workflow.models.invoice import Invoice, InvoiceStatus
from ap_workflow.models.duplicate_detection import DuplicateDetection
from ap_workflow.models.audit_log import AuditLog, AuditAction, AuditEntityType, AuditActorType
from ap_workflow.models.exception import InvoiceException, SeverityBand
from ap_workflow.core.config import settings
from ap_workflow.services import websocket_events


class DuplicateDetectionService:
    """Service for detecting duplicate invoices."""

    def __init__(self, db: Session = None):
        """Initialize duplicate detection service with database session."""
        self.db = db or next(get_session())
        self.duplicate_window_hours = settings.duplicate_detection_window_hours

    def compute_hash(self, vendor_key: str, invoice_number: str, total_amount_usd: Decimal, invoice_date) -> str:
        """Compute SHA-256 hash for exact matching."""
        hash_input = f"{vendor_key}{invoice_number}{total_amount_usd}{invoice_date}"
        return hashlib.sha256(hash_input.encode()).hexdigest()

    def compute_fuzzy_confidence(
        self,
        amount_a: Decimal,
        amount_b: Decimal,
        date_a,
        date_b,
        vendor_name_a: str,
        vendor_name_b: str
    ) -> float:
        """Compute fuzzy matching confidence."""
        from rapidfuzz import fuzz

        # Amount similarity
        max_amount = max(amount_a, amount_b)
        amount_similarity = 1 - abs(amount_a - amount_b) / max_amount if max_amount > 0 else 0

        # Date proximity
        days_apart = abs((date_b - date_a).days)
        date_proximity = max(0, 1 - (days_apart / 7))

        # Vendor match
        vendor_match = fuzz.token_set_ratio(vendor_name_a, vendor_name_b) / 100

        # Weighted combination
        fuzzy_confidence = (
            0.5 * amount_similarity +
            0.3 * date_proximity +
            0.2 * vendor_match
        )

        return round(fuzzy_confidence, 2)

    def detect_exact_duplicate(
        self,
        vendor_key: str,
        invoice_number: str,
        total_amount_usd: Decimal,
        invoice_date
    ) -> Optional[Invoice]:
        """Detect exact duplicate using hash."""
        hash_value = self.compute_hash(vendor_key, invoice_number, total_amount_usd, invoice_date)

        cutoff = datetime.utcnow() - timedelta(hours=self.duplicate_window_hours)

        existing = self.db.query(Invoice).filter(
            Invoice.vendor_key == vendor_key,
            Invoice.invoice_number == invoice_number,
            Invoice.total_amount_usd == total_amount_usd,
            Invoice.invoice_date == invoice_date,
            Invoice.received_at >= cutoff
        ).first()

        return existing

    def detect_fuzzy_duplicate(self, invoice: Invoice) -> Optional[tuple[Invoice, float]]:
        """Detect fuzzy duplicate using weighted similarity."""
        cutoff = datetime.utcnow() - timedelta(hours=self.duplicate_window_hours)

        # Get recent invoices from same vendor
        recent_invoices = self.db.query(Invoice).filter(
            Invoice.vendor_key == invoice.vendor_key,
            Invoice.invoice_id != invoice.invoice_id,
            Invoice.received_at >= cutoff
        ).all()

        for existing in recent_invoices:
            fuzzy_confidence = self.compute_fuzzy_confidence(
                invoice.total_amount_usd or invoice.total_amount,
                existing.total_amount_usd or existing.total_amount,
                invoice.invoice_date,
                existing.invoice_date,
                invoice.vendor_name,
                existing.vendor_name
            )

            if fuzzy_confidence >= 0.85:
                return existing, fuzzy_confidence

        return None

    def _find_exact_duplicate(self, vendor_key: str, invoice_number: str, total_amount_usd: Decimal, invoice_date) -> Optional[Invoice]:
        """Internal exact duplicate search."""
        return self.detect_exact_duplicate(vendor_key, invoice_number, total_amount_usd, invoice_date)

    def _is_fuzzy_duplicate(self, invoice: Invoice) -> Optional[tuple[Invoice, float]]:
        """Internal fuzzy duplicate check."""
        return self.detect_fuzzy_duplicate(invoice)

    def perform_duplicate_detection(self, invoice_id: str) -> Optional[DuplicateDetection]:
        """Perform duplicate detection for invoice."""
        invoice = self.db.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        # Try exact match first
        existing = self._find_exact_duplicate(
            invoice.vendor_key,
            invoice.invoice_number,
            invoice.total_amount_usd or invoice.total_amount,
            invoice.invoice_date
        )

        if existing:
            # Create duplicate detection record
            duplicate = DuplicateDetection(
                invoice_id=invoice_id,
                duplicate_of_invoice_id=existing.invoice_id,
                detection_type="EXACT",
                fuzzy_confidence=None
            )

            self.db.add(duplicate)
            self.db.commit()
            self.db.refresh(duplicate)

            # Create exception
            exception = InvoiceException(
                invoice_id=invoice_id,
                exception_type="DUPLICATE_EXACT",
                severity=Decimal("0.95"),
                severity_band=SeverityBand.CRITICAL.value,
                details_json=f"Duplicate of invoice {existing.invoice_id}"
            )

            self.db.add(exception)
            self.db.commit()
            self.db.refresh(exception)
            websocket_events.publish_exception_created(exception, invoice)

            return duplicate

        # Try fuzzy match
        result = self._is_fuzzy_duplicate(invoice)
        if result:
            existing, fuzzy_confidence = result

            # Create duplicate detection record
            duplicate = DuplicateDetection(
                invoice_id=invoice_id,
                duplicate_of_invoice_id=existing.invoice_id,
                detection_type="FUZZY",
                fuzzy_confidence=fuzzy_confidence
            )

            self.db.add(duplicate)
            self.db.commit()
            self.db.refresh(duplicate)

            # Create exception
            exception = InvoiceException(
                invoice_id=invoice_id,
                exception_type="DUPLICATE_FUZZY",
                severity=Decimal(str(fuzzy_confidence)),
                severity_band=SeverityBand.HIGH.value if fuzzy_confidence >= 0.9 else SeverityBand.MEDIUM.value,
                details_json=f"Fuzzy match with invoice {existing.invoice_id}, confidence: {fuzzy_confidence}"
            )

            self.db.add(exception)
            self.db.commit()
            self.db.refresh(exception)
            websocket_events.publish_exception_created(exception, invoice)

            return duplicate

        return None

    def get_duplicate_detection(self, invoice_id: str) -> Optional[DuplicateDetection]:
        """Get duplicate detection for invoice."""
        return self.db.query(DuplicateDetection).filter(
            DuplicateDetection.invoice_id == invoice_id
        ).first()
