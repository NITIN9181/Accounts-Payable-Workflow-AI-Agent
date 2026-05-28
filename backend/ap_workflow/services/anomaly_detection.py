"""Anomaly detection service for AP Workflow Agent."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from ap_workflow.database.session import get_session
from ap_workflow.models.invoice import Invoice, InvoiceStatus
from ap_workflow.models.anomaly_detection import AnomalyDetection
from ap_workflow.models.audit_log import AuditLog, AuditAction, AuditEntityType, AuditActorType
from ap_workflow.models.exception import InvoiceException, SeverityBand
from ap_workflow.models.vendor_baseline import VendorBaseline
from ap_workflow.core.config import settings
from ap_workflow.services import websocket_events


class AnomalyDetectionService:
    """Service for detecting anomalies using ensemble ML models."""

    def __init__(self, db: Session = None):
        """Initialize anomaly detection service with database session."""
        self.db = db or next(get_session())
        self.zscore_threshold = settings.zscore_threshold
        self.zscore_max_severity = settings.zscore_max_severity

    def _calculate_zscore_severity(self, amount: Decimal, mean: Decimal, std: Decimal) -> float:
        """Internal Z-Score severity calculation."""
        zscore = self.compute_zscore(amount, mean, std)
        return self.compute_severity_raw_zscore(zscore)

    def _extract_features(self, invoice: Invoice, vendor_baseline: VendorBaseline) -> Dict[str, Any]:
        """Internal feature vector extraction."""
        return self.extract_feature_vector(invoice, vendor_baseline)

        # Get historical data for vendor
        thirty_days_ago = dt.utcnow() - timedelta(days=30)
        ninety_days_ago = dt.utcnow() - timedelta(days=90)

        # Count invoices in past 30 days
        invoice_count_30d = self.db.query(func.count(Invoice.invoice_id)).filter(
            Invoice.vendor_key == invoice.vendor_key,
            Invoice.received_at >= thirty_days_ago
        ).scalar()

        # Compute mean_90d
        mean_90d_result = self.db.query(func.avg(Invoice.total_amount_usd)).filter(
            Invoice.vendor_key == invoice.vendor_key,
            Invoice.received_at >= ninety_days_ago
        ).scalar()

        mean_90d = mean_90d_result or 0

        # Compute days_since_last_invoice
        last_invoice = self.db.query(Invoice).filter(
            Invoice.vendor_key == invoice.vendor_key,
            Invoice.received_at < invoice.received_at
        ).order_by(Invoice.received_at.desc()).first()

        days_since_last_invoice = 0
        if last_invoice:
            days_since_last_invoice = (invoice.received_at - last_invoice.received_at).days

        # Compute amount_vs_p95
        p95_amount = vendor_baseline.p95_invoice_amount_90d or 0
        amount_vs_p95 = float(invoice.total_amount_usd) / p95_amount if p95_amount > 0 else 0

        # Compute amount_delta_pct
        amount_delta_pct = ((float(invoice.total_amount_usd) - mean_90d) / mean_90d * 100) if mean_90d > 0 else 0

        # Extract time features
        hour_of_day = invoice.received_at.hour
        day_of_week = invoice.received_at.weekday()
        is_weekend = 1 if day_of_week >= 5 else 0
        is_month_end = 1 if invoice.received_at.day >= 25 else 0
        is_quarter_end = (
            1 if invoice.received_at.month in [3, 6, 9, 12] and invoice.received_at.day >= 25
            else 0
        )

        # Compute z_score_30d
        mean_30d = vendor_baseline.mean_invoice_amount_30d or 0
        std_30d = vendor_baseline.std_invoice_amount_30d or 0
        z_score_30d = self.compute_zscore(invoice.total_amount_usd, mean_30d, std_30d)

        # Compute invoice_frequency_7d
        seven_days_ago = dt.utcnow() - timedelta(days=7)
        invoice_frequency_7d = self.db.query(func.count(Invoice.invoice_id)).filter(
            Invoice.vendor_key == invoice.vendor_key,
            Invoice.received_at >= seven_days_ago
        ).scalar()

        return {
            "total_amount_usd": float(invoice.total_amount_usd),
            "log_amount": float(invoice.total_amount_usd + 1).log(),
            "z_score_30d": z_score_30d,
            "days_since_last_invoice": days_since_last_invoice,
            "invoice_frequency_7d": invoice_frequency_7d,
            "amount_vs_p95": amount_vs_p95,
            "hour_of_day": hour_of_day,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "is_month_end": is_month_end,
            "is_quarter_end": is_quarter_end,
            "invoice_count_30d": invoice_count_30d,
            "mean_90d": mean_90d,
            "amount_delta_pct": amount_delta_pct
        }

    def _combine_scores(self, scores: List[float]) -> float:
        """Internal ensemble combination logic."""
        detected_count = sum(1 for s in scores if s > 0.4)

        if detected_count == 0:
            return 0.0
        elif detected_count == 1:
            return min(1.0, max(scores) * 0.95)
        elif detected_count == 2:
            sorted_scores = sorted(scores, reverse=True)
            return min(1.0, sorted_scores[0] * 1.10)
        else:
            return min(1.0, max(scores) * 1.20)

    def detect_anomalies(self, invoice_id: str) -> Optional[AnomalyDetection]:
        """Perform anomaly detection for invoice using ensemble models."""
        invoice = self.db.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        # Get vendor baseline
        vendor_baseline = self.db.query(VendorBaseline).filter(
            VendorBaseline.vendor_key == invoice.vendor_key
        ).first()

        # Compute Z-Score severity
        severity_raw_zscore = 0.0
        if vendor_baseline and vendor_baseline.mean_invoice_amount_30d:
            zscore = self.compute_zscore(
                invoice.total_amount_usd,
                vendor_baseline.mean_invoice_amount_30d,
                vendor_baseline.std_invoice_amount_30d or 0
            )
            severity_raw_zscore = self.compute_severity_raw_zscore(zscore)

        # Extract feature vector for Isolation Forest
        feature_vector = self.extract_feature_vector(invoice, vendor_baseline or VendorBaseline())

        # Compute Isolation Forest severity (simulated)
        severity_raw_isolation_forest = 0.0  # Would use trained model

        # Get duplicate detection severity
        severity_raw_duplicate = 0.0

        # Combine using ensemble logic
        scores = [severity_raw_zscore, severity_raw_isolation_forest, severity_raw_duplicate]
        final_severity = self._combine_scores(scores)

        # Assign severity band
        if final_severity > 0.8:
            severity_band = SeverityBand.CRITICAL.value
        elif final_severity >= 0.6:
            severity_band = SeverityBand.HIGH.value
        elif final_severity >= 0.4:
            severity_band = SeverityBand.MEDIUM.value
        else:
            severity_band = SeverityBand.LOW.value

        # Create anomaly detection record
        anomaly_detection = AnomalyDetection(
            invoice_id=invoice_id,
            vendor_key=invoice.vendor_key,
            severity_raw_zscore=severity_raw_zscore,
            severity_raw_isolation_forest=severity_raw_isolation_forest,
            severity_raw_duplicate=severity_raw_duplicate,
            final_severity=final_severity,
            severity_band=severity_band,
            feature_vector=feature_vector
        )

        self.db.add(anomaly_detection)
        self.db.commit()
        self.db.refresh(anomaly_detection)

        # Create exception if severity > 0.4
        if final_severity > 0.4:
            exception = InvoiceException(
                invoice_id=invoice_id,
                exception_type="ANOMALY",
                severity=final_severity,
                severity_band=severity_band,
                details_json=f"Anomaly detected with ensemble score: {final_severity}"
            )
            self.db.add(exception)
            self.db.commit()
            self.db.refresh(exception)
            websocket_events.publish_exception_created(exception, invoice)

        # Create audit log
        audit_log = AuditLog(
            actor_type=AuditActorType.SYSTEM,
            action_type=AuditAction.EXCEPTION_CREATED,
            entity_type=AuditEntityType.INVOICE,
            entity_id=invoice_id,
            after_state={"final_severity": final_severity, "severity_band": severity_band}
        )
        self.db.add(audit_log)
        self.db.commit()

        return anomaly_detection

    def get_anomaly_detection(self, invoice_id: str) -> Optional[AnomalyDetection]:
        """Get anomaly detection for invoice."""
        return self.db.query(AnomalyDetection).filter(
            AnomalyDetection.invoice_id == invoice_id
        ).first()
