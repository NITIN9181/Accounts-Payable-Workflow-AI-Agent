"""Vendor baseline models for AP Workflow Agent."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DECIMAL, DateTime, Integer, Float
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from ap_workflow.database.session import Base


class VendorBaseline(Base):
    """Vendor baseline model storing statistical vendor profiles."""

    __tablename__ = "vendor_baselines"

    vendor_key = Column(String(100), primary_key=True)
    vendor_name = Column(String(100))
    txn_count_total = Column(Integer, default=0)
    mean_invoice_amount_30d = Column(DECIMAL(12, 2))
    std_invoice_amount_30d = Column(DECIMAL(12, 2))
    p95_invoice_amount_90d = Column(DECIMAL(12, 2))
    avg_days_to_pay_90d = Column(Float)
    auto_approve_max_amount = Column(DECIMAL(12, 2))
    auto_approve_max_zscore = Column(Float)
    preferred_payment_method = Column(String(50))  # ACH, WIRE, CHECK
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<VendorBaseline(vendor_key={self.vendor_key}, mean_invoice_amount_30d={self.mean_invoice_amount_30d})>"
