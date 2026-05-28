"""Vendor baseline history model for AP Workflow Agent."""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, String, DECIMAL, DateTime, Integer, Float
from sqlalchemy.dialects.postgresql import UUID as PGUUID
import uuid

from ap_workflow.database.session import Base

class VendorBaselineHistory(Base):
    """Model for storing historical snapshots of vendor baselines."""

    __tablename__ = "vendor_baseline_history"

    history_id = Column(PGUUID, primary_key=True, default=uuid.uuid4)
    vendor_key = Column(String(100), nullable=False, index=True)
    
    # Snapshot of statistics
    mean_invoice_amount_30d = Column(DECIMAL(12, 2))
    std_invoice_amount_30d = Column(DECIMAL(12, 2))
    p95_invoice_amount_90d = Column(DECIMAL(12, 2))
    avg_days_to_pay_90d = Column(Float)
    txn_count_total = Column(Integer)
    
    # Snapshot of configuration
    auto_approve_max_amount = Column(DECIMAL(12, 2))
    auto_approve_max_zscore = Column(Float)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<VendorBaselineHistory(vendor_key={self.vendor_key}, created_at={self.created_at})>"
