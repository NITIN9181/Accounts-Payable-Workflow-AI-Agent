#!/usr/bin/env python
"""Initialize database with tables and demo data."""

import sys
from ap_workflow.database.session import engine, Base
from ap_workflow.models import (
    Invoice, InvoiceLineItem, OCRExtraction, PurchaseOrder, POLineItem,
    Receipt, ReceiptLineItem, MatchingResult, DuplicateDetection,
    AnomalyDetection, InvoiceException, Approval, Payment, PaymentBatch,
    AuditLog, VendorBaseline, LLMExplanationCache, LLMRequest
)

def init_db():
    """Create all tables and seed demo data."""
    print("Creating database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ Database tables created successfully")
    except Exception as e:
        print(f"✗ Error creating tables: {e}")
        return False
    
    print("Seeding demo data...")
    try:
        from seed_demo_data import seed_demo_data
        seed_demo_data()
        print("✓ Demo data seeded successfully")
    except Exception as e:
        print(f"✗ Error seeding data: {e}")
        # Don't fail if seeding fails - tables are still created
        return True
    
    return True

if __name__ == "__main__":
    success = init_db()
    sys.exit(0 if success else 1)

