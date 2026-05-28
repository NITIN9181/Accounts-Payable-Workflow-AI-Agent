"""Anomaly detection models for AP Workflow Agent."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, String, DECIMAL, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship

from ap_workflow.database.session import Base


class AnomalyDetection(Base):
    """Anomaly detection model storing ensemble anomaly scores."""

    __tablename__ = "anomaly_detections"

    anomaly_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_id = Column(PGUUID(as_uuid=True), ForeignKey("invoices.invoice_id"), nullable=False, unique=True)
    vendor_key = Column(String(100), nullable=False)
    severity_raw_zscore = Column(DECIMAL(3, 2))
    severity_raw_isolation_forest = Column(DECIMAL(3, 2))
    severity_raw_duplicate = Column(DECIMAL(3, 2))
    final_severity = Column(DECIMAL(3, 2), nullable=False)
    severity_band = Column(String(20))  # CRITICAL, HIGH, MEDIUM, LOW
    feature_vector = Column(JSONB)  # 14-dimensional feature vector
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    invoice = relationship("Invoice", back_populates="anomaly_detections")

    def __repr__(self) -> str:
        return f"<AnomalyDetection(anomaly_id={self.anomaly_id}, invoice_id={self.invoice_id}, final_severity={self.final_severity})>"
