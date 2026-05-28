"""
Seed script — populates the database with realistic demo data.

Guarantees:
  - 6 PENDING items in AP_CLERK_QUEUE   (invoices $500 – $4,999)
  - 4 PENDING items in MANAGER_QUEUE    (invoices $5,001 – $24,999)
  - 3 PENDING items in CFO_ESCALATION_QUEUE (invoices $25,001 – $95,000)
  - ~50 historical invoices across 8 vendors
  - ~30 scheduled/executed payments

Run from the backend directory:
    python seed_demo_data.py
"""

import sys
import os
import random
import hashlib
from datetime import datetime, date, timedelta
from decimal import Decimal
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from ap_workflow.database.session import SessionLocal
from ap_workflow.models.invoice import Invoice, InvoiceLineItem, InvoiceStatus
from ap_workflow.models.payment import Payment, PaymentMethod
from ap_workflow.models.vendor_baseline import VendorBaseline
from ap_workflow.models.exception import InvoiceException, SeverityBand
from ap_workflow.models.approval import Approval

# ── helpers ───────────────────────────────────────────────────────────────────

def days_ago(n: int) -> date:
    return date.today() - timedelta(days=n)

def days_ahead(n: int) -> date:
    return date.today() + timedelta(days=n)

def file_hash(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()

def make_invoice(db, vendor_key, vendor_name, amount, status, inv_date, due_date, tag=""):
    inv_number = f"INV-{vendor_key[:4].upper()}-{random.randint(10000,99999)}{tag}"
    fh = file_hash(f"{vendor_key}-{inv_number}-{amount}")
    if db.query(Invoice).filter_by(file_hash=fh).first():
        fh = file_hash(f"{vendor_key}-{inv_number}-{amount}-{uuid4()}")
    inv = Invoice(
        invoice_id=uuid4(),
        vendor_key=vendor_key,
        vendor_name=vendor_name,
        invoice_number=inv_number,
        total_amount=Decimal(str(amount)),
        total_amount_usd=Decimal(str(amount)),
        tax_amount=Decimal(str(round(amount * 0.08, 2))),
        invoice_date=inv_date,
        due_date=due_date,
        po_reference=f"PO-{random.randint(1000,9999)}" if random.random() > 0.15 else None,
        currency_code="USD",
        fx_rate=Decimal("1.000000"),
        file_hash=fh,
        file_path=f"/invoices/{vendor_key}/{inv_number}.pdf",
        ingestion_source=random.choice(["email", "upload"]),
        status=status,
        received_at=datetime.combine(inv_date, datetime.min.time()),
        demo_mode=True,
    )
    db.add(inv)
    db.flush()

    # 1–3 line items
    remaining = amount
    n = random.randint(1, 3)
    templates = [
        ("Professional Services", 1), ("Software License", 1),
        ("Office Supplies", 10), ("Consulting Hours", 8),
        ("Cloud Hosting", 1), ("Catering Services", 1),
        ("Printing & Design", 5), ("Logistics & Freight", 1),
    ]
    for j in range(n):
        desc, qty = random.choice(templates)
        line_total = round(remaining if j == n - 1 else remaining * random.uniform(0.3, 0.6), 2)
        remaining -= line_total
        unit = round(line_total / qty, 2)
        db.add(InvoiceLineItem(
            invoice_id=inv.invoice_id,
            description=desc,
            quantity=Decimal(str(qty)),
            unit_price=Decimal(str(unit)),
            line_total=Decimal(str(line_total)),
        ))
    return inv

def make_exception(db, invoice, exc_type, severity_band, severity_score, explanation, resolved=False):
    exc = InvoiceException(
        exception_id=uuid4(),
        invoice_id=invoice.invoice_id,
        exception_type=exc_type,
        severity=Decimal(str(severity_score)),
        severity_band=severity_band.value,
        llm_explanation=explanation,
        llm_explanation_ready=True,
        llm_explanation_fallback=False,
        resolved=resolved,
    )
    db.add(exc)
    db.flush()
    return exc

def make_approval(db, invoice, exc, queue, role, status, received_at):
    sla_hours = {"AP_CLERK": 4, "MANAGER": 24, "CFO": 48}[role]
    sla_deadline = received_at + timedelta(hours=sla_hours)
    approval = Approval(
        approval_id=uuid4(),
        invoice_id=invoice.invoice_id,
        exception_id=exc.exception_id,
        approval_queue=queue,
        status=status,
        approver_id=None,
        approver_role=role if status != "PENDING" else None,
        notes="Auto-seeded" if status != "PENDING" else None,
        sla_deadline=sla_deadline,
        sla_violated=datetime.utcnow() > sla_deadline and status == "PENDING",
        created_at=received_at,
    )
    db.add(approval)
    db.flush()
    return approval

def make_payment(db, invoice, pay_date, pay_status):
    db.add(Payment(
        payment_id=uuid4(),
        invoice_id=invoice.invoice_id,
        scheduled_payment_date=pay_date,
        payment_method=random.choice(["ACH", "WIRE", "CHECK"]),
        payment_amount=invoice.total_amount_usd,
        discount_captured=Decimal("0.00"),
        status=pay_status,
    ))

# ── vendor catalogue ──────────────────────────────────────────────────────────

VENDORS = [
    {"key": "acme_supplies",     "name": "Acme Office Supplies",   "mean": 1_200,  "method": "ACH"},
    {"key": "techpro_it",        "name": "TechPro IT Solutions",   "mean": 8_500,  "method": "WIRE"},
    {"key": "global_logistics",  "name": "Global Logistics Co.",   "mean": 15_000, "method": "ACH"},
    {"key": "premier_catering",  "name": "Premier Catering Ltd.",  "mean": 3_400,  "method": "CHECK"},
    {"key": "skyline_realty",    "name": "Skyline Realty Group",   "mean": 45_000, "method": "WIRE"},
    {"key": "delta_consulting",  "name": "Delta Consulting Inc.",  "mean": 22_000, "method": "ACH"},
    {"key": "rapid_print",       "name": "Rapid Print & Design",   "mean": 900,    "method": "CHECK"},
    {"key": "nexus_cloud",       "name": "Nexus Cloud Services",   "mean": 6_200,  "method": "ACH"},
]

EXCEPTION_TYPES = [
    ("PO_MISMATCH",     SeverityBand.HIGH,     0.75, "Invoice amount deviates significantly from the approved PO value."),
    ("DUPLICATE_FUZZY", SeverityBand.CRITICAL, 0.95, "A near-duplicate invoice was detected from the same vendor within 30 days."),
    ("RECEIPT_MISSING", SeverityBand.MEDIUM,   0.55, "No goods receipt has been recorded against this invoice."),
    ("INCOMPLETE_DATA", SeverityBand.LOW,       0.30, "One or more required fields (PO reference, tax ID) are missing."),
    ("PO_MISSING",      SeverityBand.HIGH,      0.80, "No purchase order reference found for this invoice."),
]

# ── guaranteed pending queue items ───────────────────────────────────────────
# Each entry: (vendor_key, vendor_name, amount, queue, role, exc_type, severity_band, score, explanation)

CLERK_QUEUE_ITEMS = [
    ("acme_supplies",    "Acme Office Supplies",  1_150.00, "AP_CLERK_QUEUE", "AP_CLERK",
     "PO_MISMATCH",     SeverityBand.HIGH,   0.75, "Invoice amount deviates from the approved PO value."),
    ("rapid_print",      "Rapid Print & Design",    875.50, "AP_CLERK_QUEUE", "AP_CLERK",
     "INCOMPLETE_DATA", SeverityBand.LOW,    0.30, "PO reference field is missing on this invoice."),
    ("premier_catering", "Premier Catering Ltd.",  3_200.00, "AP_CLERK_QUEUE", "AP_CLERK",
     "RECEIPT_MISSING", SeverityBand.MEDIUM, 0.55, "No goods receipt has been recorded against this invoice."),
    ("acme_supplies",    "Acme Office Supplies",  4_800.00, "AP_CLERK_QUEUE", "AP_CLERK",
     "PO_MISSING",      SeverityBand.HIGH,   0.80, "No purchase order reference found for this invoice."),
    ("rapid_print",      "Rapid Print & Design",    620.00, "AP_CLERK_QUEUE", "AP_CLERK",
     "DUPLICATE_FUZZY", SeverityBand.CRITICAL, 0.95, "A near-duplicate invoice was detected from the same vendor within 30 days."),
    ("premier_catering", "Premier Catering Ltd.",  2_750.00, "AP_CLERK_QUEUE", "AP_CLERK",
     "PO_MISMATCH",     SeverityBand.HIGH,   0.75, "Invoice total is 18% above the PO approved amount."),
]

MANAGER_QUEUE_ITEMS = [
    ("techpro_it",       "TechPro IT Solutions",   8_400.00, "MANAGER_QUEUE", "MANAGER",
     "PO_MISMATCH",     SeverityBand.HIGH,   0.75, "Invoice amount deviates significantly from the approved PO value."),
    ("nexus_cloud",      "Nexus Cloud Services",  12_500.00, "MANAGER_QUEUE", "MANAGER",
     "RECEIPT_MISSING", SeverityBand.MEDIUM, 0.55, "No goods receipt has been recorded against this invoice."),
    ("delta_consulting", "Delta Consulting Inc.", 19_800.00, "MANAGER_QUEUE", "MANAGER",
     "PO_MISSING",      SeverityBand.HIGH,   0.80, "No purchase order reference found for this invoice."),
    ("global_logistics", "Global Logistics Co.",  14_200.00, "MANAGER_QUEUE", "MANAGER",
     "DUPLICATE_FUZZY", SeverityBand.CRITICAL, 0.95, "A near-duplicate invoice was detected from the same vendor within 30 days."),
]

CFO_QUEUE_ITEMS = [
    ("skyline_realty",   "Skyline Realty Group",  48_000.00, "CFO_ESCALATION_QUEUE", "CFO",
     "PO_MISMATCH",     SeverityBand.HIGH,   0.75, "Invoice amount deviates significantly from the approved PO value."),
    ("delta_consulting", "Delta Consulting Inc.", 67_500.00, "CFO_ESCALATION_QUEUE", "CFO",
     "RECEIPT_MISSING", SeverityBand.MEDIUM, 0.55, "No goods receipt has been recorded against this invoice."),
    ("skyline_realty",   "Skyline Realty Group",  92_000.00, "CFO_ESCALATION_QUEUE", "CFO",
     "DUPLICATE_FUZZY", SeverityBand.CRITICAL, 0.95, "A near-duplicate invoice was detected from the same vendor within 30 days."),
]

# ── main ──────────────────────────────────────────────────────────────────────

def seed():
    db = SessionLocal()
    try:
        # 1. Vendor baselines
        print("Seeding vendor baselines...")
        for v in VENDORS:
            if db.query(VendorBaseline).filter_by(vendor_key=v["key"]).first():
                continue
            mean = v["mean"]
            db.add(VendorBaseline(
                vendor_key=v["key"],
                vendor_name=v["name"],
                txn_count_total=random.randint(40, 200),
                mean_invoice_amount_30d=Decimal(str(mean)),
                std_invoice_amount_30d=Decimal(str(round(mean * 0.15, 2))),
                p95_invoice_amount_90d=Decimal(str(round(mean * 1.6, 2))),
                avg_days_to_pay_90d=round(random.uniform(12, 35), 1),
                auto_approve_max_amount=Decimal(str(round(mean * 1.3, 2))),
                auto_approve_max_zscore=2.5,
                preferred_payment_method=v["method"],
            ))
        db.commit()
        print(f"  ✓ {len(VENDORS)} vendor baselines")

        # 2. Historical invoices (background data — mix of statuses)
        print("Seeding historical invoices...")
        hist_count = 0
        hist_invoices = []
        for v in VENDORS:
            for i in range(random.randint(5, 8)):
                mean = v["mean"]
                amount = round(mean * random.uniform(0.70, 1.30), 2)
                inv_date = days_ago(random.randint(10, 90))
                due = inv_date + timedelta(days=random.choice([30, 45, 60]))
                days_old = (date.today() - inv_date).days
                if days_old > 60:
                    status = random.choice([InvoiceStatus.PAID, InvoiceStatus.APPROVED])
                elif days_old > 30:
                    status = random.choice([InvoiceStatus.APPROVED, InvoiceStatus.SCHEDULED])
                else:
                    status = random.choice([InvoiceStatus.PENDING_APPROVAL, InvoiceStatus.APPROVED])
                inv = make_invoice(db, v["key"], v["name"], amount, status, inv_date, due, tag=f"-h{i}")
                hist_invoices.append(inv)
                hist_count += 1
        db.commit()
        print(f"  ✓ {hist_count} historical invoices")

        # 3. Guaranteed pending queue items
        print("Seeding guaranteed queue items...")
        queue_invoices = []  # (invoice, exc, queue, role)

        all_queue_items = (
            [(item, "clerk") for item in CLERK_QUEUE_ITEMS] +
            [(item, "manager") for item in MANAGER_QUEUE_ITEMS] +
            [(item, "cfo") for item in CFO_QUEUE_ITEMS]
        )

        for item, _ in all_queue_items:
            vkey, vname, amount, queue, role, exc_type, sev_band, sev_score, explanation = item
            inv_date = days_ago(random.randint(1, 7))  # recent — clearly pending
            due = inv_date + timedelta(days=30)
            inv = make_invoice(db, vkey, vname, amount, InvoiceStatus.PENDING_APPROVAL, inv_date, due, tag="-q")
            exc = make_exception(db, inv, exc_type, sev_band, sev_score, explanation, resolved=False)
            approval = make_approval(db, inv, exc, queue, role, "PENDING", inv.received_at)
            queue_invoices.append((inv, exc, queue, role))

        db.commit()
        print(f"  ✓ {len(CLERK_QUEUE_ITEMS)} items in AP_CLERK_QUEUE")
        print(f"  ✓ {len(MANAGER_QUEUE_ITEMS)} items in MANAGER_QUEUE")
        print(f"  ✓ {len(CFO_QUEUE_ITEMS)} items in CFO_ESCALATION_QUEUE")

        # 4. Exceptions on some historical invoices (resolved)
        print("Seeding historical exceptions & approvals...")
        hist_exc_count = 0
        for invoice in hist_invoices:
            if random.random() > 0.35:
                continue
            exc_type, sev_band, sev_score, explanation = random.choice(EXCEPTION_TYPES)
            resolved = invoice.status in (InvoiceStatus.APPROVED, InvoiceStatus.PAID)
            exc = make_exception(db, invoice, exc_type, sev_band, sev_score, explanation, resolved=resolved)
            amount = float(invoice.total_amount_usd or 0)
            if amount <= 5_000:
                queue, role = "AP_CLERK_QUEUE", "AP_CLERK"
            elif amount <= 25_000:
                queue, role = "MANAGER_QUEUE", "MANAGER"
            else:
                queue, role = "CFO_ESCALATION_QUEUE", "CFO"
            status = "APPROVED" if resolved else "PENDING"
            make_approval(db, invoice, exc, queue, role, status, invoice.received_at)
            hist_exc_count += 1
        db.commit()
        print(f"  ✓ {hist_exc_count} historical exceptions/approvals")

        # 5. Payments
        print("Seeding payments...")
        pay_count = 0
        all_invoices = hist_invoices + [inv for inv, _, _, _ in queue_invoices]
        for invoice in all_invoices:
            if invoice.status == InvoiceStatus.PAID:
                pay_date = invoice.due_date - timedelta(days=random.randint(0, 5))
                make_payment(db, invoice, pay_date, "EXECUTED")
                pay_count += 1
            elif invoice.status in (InvoiceStatus.APPROVED, InvoiceStatus.SCHEDULED):
                if random.random() < 0.70:
                    pay_date = days_ahead(random.randint(1, 30))
                    make_payment(db, invoice, pay_date, "SCHEDULED")
                    pay_count += 1
        db.commit()
        print(f"  ✓ {pay_count} payments")

        print("\n✅ Demo data seeded successfully!")
        print(f"   Vendors:              {len(VENDORS)}")
        print(f"   Historical invoices:  {hist_count}")
        print(f"   AP Clerk queue:       {len(CLERK_QUEUE_ITEMS)} pending")
        print(f"   Manager queue:        {len(MANAGER_QUEUE_ITEMS)} pending")
        print(f"   CFO queue:            {len(CFO_QUEUE_ITEMS)} pending")
        print(f"   Payments:             {pay_count}")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Seed failed: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
