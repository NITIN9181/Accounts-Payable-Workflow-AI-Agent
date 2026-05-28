"""Initial schema migration.

Revision ID: 001_initial_schema
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE invoice_status AS ENUM ('PENDING_OCR', 'PENDING_INGESTION_QUEUE', 'OCR_FAILED', 'PENDING_MANUAL_REVIEW', 'PENDING_MATCHING', 'PENDING_APPROVAL', 'APPROVED', 'HELD', 'REJECTED', 'SCHEDULED', 'PAID', 'INGESTION_FAILED')")
    op.execute("CREATE TYPE approval_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'ESCALATED')")
    op.execute("CREATE TYPE approval_queue AS ENUM ('AP_CLERK_QUEUE', 'MANAGER_QUEUE', 'CFO_ESCALATION_QUEUE')")
    op.execute("CREATE TYPE payment_method AS ENUM ('ACH', 'WIRE', 'CHECK')")
    op.execute("CREATE TYPE severity_band AS ENUM ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')")
    op.execute("CREATE TYPE audit_action AS ENUM ('invoice_created', 'ocr_extraction_completed', 'three_way_match_performed', 'exception_created', 'exception_resolved', 'approval_action_taken', 'payment_scheduled', 'invoice_status_changed', 'vendor_baseline_updated', 'approval_created', 'approval_completed', 'payment_executed')")
    op.execute("CREATE TYPE audit_entity_type AS ENUM ('INVOICE', 'EXCEPTION', 'APPROVAL', 'PAYMENT', 'VENDOR_BASELINE')")
    op.execute("CREATE TYPE audit_actor_type AS ENUM ('ANALYST', 'SYSTEM', 'API', 'VENDOR')")

    # Create tables
    op.create_table('vendor_baselines',
        sa.Column('vendor_key', sa.String(length=100), nullable=False),
        sa.Column('vendor_name', sa.String(length=100), nullable=True),
        sa.Column('txn_count_total', sa.Integer(), nullable=True),
        sa.Column('mean_invoice_amount_30d', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('std_invoice_amount_30d', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('p95_invoice_amount_90d', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('avg_days_to_pay_90d', sa.Float(), nullable=True),
        sa.Column('auto_approve_max_amount', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('auto_approve_max_zscore', sa.Float(), nullable=True),
        sa.Column('preferred_payment_method', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('vendor_key')
    )

    op.create_table('invoices',
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vendor_key', sa.String(length=100), nullable=False),
        sa.Column('vendor_name', sa.String(length=100), nullable=False),
        sa.Column('invoice_number', sa.String(length=50), nullable=False),
        sa.Column('total_amount', sa.DECIMAL(precision=12, scale=2), nullable=False),
        sa.Column('total_amount_usd', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('tax_amount', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('invoice_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('po_reference', sa.String(length=50), nullable=True),
        sa.Column('currency_code', sa.String(length=3), nullable=True),
        sa.Column('fx_rate', sa.DECIMAL(precision=10, scale=6), nullable=True),
        sa.Column('stale_fx_rate', sa.Boolean(), nullable=True),
        sa.Column('file_hash', sa.String(length=64), nullable=False),
        sa.Column('file_path', sa.String(length=255), nullable=True),
        sa.Column('ingestion_source', sa.String(length=20), nullable=True),
        sa.Column('status', sa.Enum('PENDING_OCR', 'PENDING_INGESTION_QUEUE', 'OCR_FAILED', 'PENDING_MANUAL_REVIEW', 'PENDING_MATCHING', 'PENDING_APPROVAL', 'APPROVED', 'HELD', 'REJECTED', 'SCHEDULED', 'PAID', 'INGESTION_FAILED', name='invoice_status'), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('ocr_completed_at', sa.DateTime(), nullable=True),
        sa.Column('matching_completed_at', sa.DateTime(), nullable=True),
        sa.Column('anomaly_completed_at', sa.DateTime(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('demo_mode', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('invoice_id'),
        sa.UniqueConstraint('file_hash')
    )
    op.create_index(op.f('ix_invoices_vendor_key'), 'invoices', ['vendor_key'], unique=False)

    op.create_table('purchase_orders',
        sa.Column('po_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vendor_key', sa.String(length=100), nullable=False),
        sa.Column('po_number', sa.String(length=50), nullable=False),
        sa.Column('po_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('po_id')
    )
    op.create_index(op.f('ix_purchase_orders_vendor_key'), 'purchase_orders', ['vendor_key'], unique=False)

    op.create_table('receipts',
        sa.Column('receipt_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('po_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('receipt_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('receipt_id')
    )

    op.create_table('audit_logs',
        sa.Column('log_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('actor_type', sa.String(length=50), nullable=True),
        sa.Column('action_type', sa.String(length=50), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('before_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('after_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('log_id')
    )

    op.create_table('invoice_line_items',
        sa.Column('line_item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('quantity', sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.Column('unit_price', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('line_total', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('sku', sa.String(length=50), nullable=True),
        sa.Column('po_line_number', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.invoice_id'], ),
        sa.PrimaryKeyConstraint('line_item_id')
    )

    op.create_table('ocr_extractions',
        sa.Column('extraction_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_number', sa.String(length=50), nullable=True),
        sa.Column('invoice_number_confidence', sa.DECIMAL(precision=3, scale=2), nullable=True),
        sa.Column('vendor_name', sa.String(length=100), nullable=True),
        sa.Column('vendor_name_confidence', sa.DECIMAL(precision=3, scale=2), nullable=True),
        sa.Column('total_amount', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('total_amount_confidence', sa.DECIMAL(precision=3, scale=2), nullable=True),
        sa.Column('tax_amount', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('tax_amount_confidence', sa.DECIMAL(precision=3, scale=2), nullable=True),
        sa.Column('invoice_date', sa.Date(), nullable=True),
        sa.Column('invoice_date_confidence', sa.DECIMAL(precision=3, scale=2), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('due_date_confidence', sa.DECIMAL(precision=3, scale=2), nullable=True),
        sa.Column('po_reference', sa.String(length=50), nullable=True),
        sa.Column('po_reference_confidence', sa.DECIMAL(precision=3, scale=2), nullable=True),
        sa.Column('ocr_raw_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.invoice_id'], ),
        sa.PrimaryKeyConstraint('extraction_id'),
        sa.UniqueConstraint('invoice_id')
    )

    op.create_table('po_line_items',
        sa.Column('po_line_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('po_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=True),
        sa.Column('sku', sa.String(length=50), nullable=True),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('quantity', sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.Column('unit_price', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['po_id'], ['purchase_orders.po_id'], ),
        sa.PrimaryKeyConstraint('po_line_id')
    )

    op.create_table('receipt_line_items',
        sa.Column('receipt_line_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('receipt_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('po_line_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('received_quantity', sa.DECIMAL(precision=12, scale=4), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['po_line_id'], ['po_line_items.po_line_id'], ),
        sa.ForeignKeyConstraint(['receipt_id'], ['receipts.receipt_id'], ),
        sa.PrimaryKeyConstraint('receipt_line_id')
    )

    op.create_table('matching_results',
        sa.Column('matching_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('po_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('match_status', sa.String(length=50), nullable=True),
        sa.Column('variance_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.invoice_id'], ),
        sa.ForeignKeyConstraint(['po_id'], ['purchase_orders.po_id'], ),
        sa.PrimaryKeyConstraint('matching_id'),
        sa.UniqueConstraint('invoice_id')
    )

    op.create_table('duplicate_detections',
        sa.Column('duplicate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('duplicate_of_invoice_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('detection_type', sa.String(length=20), nullable=True),
        sa.Column('fuzzy_confidence', sa.DECIMAL(precision=3, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['duplicate_of_invoice_id'], ['invoices.invoice_id'], ),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.invoice_id'], ),
        sa.PrimaryKeyConstraint('duplicate_id')
    )

    op.create_table('anomaly_detections',
        sa.Column('anomaly_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vendor_key', sa.String(length=100), nullable=False),
        sa.Column('severity_raw_zscore', sa.DECIMAL(precision=3, scale=2), nullable=True),
        sa.Column('severity_raw_isolation_forest', sa.DECIMAL(precision=3, scale=2), nullable=True),
        sa.Column('severity_raw_duplicate', sa.DECIMAL(precision=3, scale=2), nullable=True),
        sa.Column('final_severity', sa.DECIMAL(precision=3, scale=2), nullable=False),
        sa.Column('severity_band', sa.String(length=20), nullable=True),
        sa.Column('feature_vector', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.invoice_id'], ),
        sa.PrimaryKeyConstraint('anomaly_id'),
        sa.UniqueConstraint('invoice_id')
    )

    op.create_table('invoice_exceptions',
        sa.Column('exception_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('exception_type', sa.String(length=50), nullable=True),
        sa.Column('severity', sa.DECIMAL(precision=3, scale=2), nullable=False),
        sa.Column('severity_band', sa.String(length=20), nullable=True),
        sa.Column('details_json', sa.String(), nullable=True),
        sa.Column('llm_explanation', sa.String(), nullable=True),
        sa.Column('llm_explanation_fallback', sa.Boolean(), nullable=True),
        sa.Column('llm_explanation_ready', sa.Boolean(), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.invoice_id'], ),
        sa.PrimaryKeyConstraint('exception_id')
    )

    op.create_table('approvals',
        sa.Column('approval_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('exception_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approver_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approver_role', sa.String(length=50), nullable=True),
        sa.Column('approval_queue', sa.String(length=50), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'APPROVED', 'REJECTED', 'ESCALATED', name='approval_status'), nullable=True),
        sa.Column('sla_deadline', sa.DateTime(), nullable=False),
        sa.Column('sla_violated', sa.Boolean(), nullable=True),
        sa.Column('notes', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['exception_id'], ['invoice_exceptions.exception_id'], ),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.invoice_id'], ),
        sa.PrimaryKeyConstraint('approval_id')
    )

    op.create_table('payments',
        sa.Column('payment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scheduled_payment_date', sa.Date(), nullable=False),
        sa.Column('payment_method', sa.String(length=50), nullable=True),
        sa.Column('payment_amount', sa.DECIMAL(precision=12, scale=2), nullable=False),
        sa.Column('discount_captured', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.invoice_id'], ),
        sa.PrimaryKeyConstraint('payment_id')
    )

    op.create_table('payment_batches',
        sa.Column('batch_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scheduled_payment_date', sa.Date(), nullable=False),
        sa.Column('total_outflow', sa.DECIMAL(precision=14, scale=2), nullable=True),
        sa.Column('invoice_count', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('batch_id')
    )

    op.create_table('llm_explanation_cache',
        sa.Column('cache_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cache_key', sa.String(length=64), nullable=False),
        sa.Column('vendor_key', sa.String(length=100), nullable=True),
        sa.Column('exception_type', sa.String(length=50), nullable=True),
        sa.Column('explanation', sa.String(), nullable=False),
        sa.Column('fallback', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True),
        sa.Column('ttl_expires_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('cache_id'),
        sa.UniqueConstraint('cache_key')
    )

    op.create_table('llm_requests',
        sa.Column('request_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('exception_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('queue_position', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['exception_id'], ['invoice_exceptions.exception_id'], ),
        sa.PrimaryKeyConstraint('request_id')
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('llm_requests')
    op.drop_table('llm_explanation_cache')
    op.drop_table('payment_batches')
    op.drop_table('payments')
    op.drop_table('approvals')
    op.drop_table('invoice_exceptions')
    op.drop_table('anomaly_detections')
    op.drop_table('duplicate_detections')
    op.drop_table('matching_results')
    op.drop_table('receipt_line_items')
    op.drop_table('po_line_items')
    op.drop_table('ocr_extractions')
    op.drop_table('invoice_line_items')
    op.drop_table('audit_logs')
    op.drop_table('receipts')
    op.drop_table('purchase_orders')
    op.drop_index(op.f('ix_invoices_vendor_key'), table_name='invoices')
    op.drop_table('invoices')
    op.drop_table('vendor_baselines')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS invoice_status")
    op.execute("DROP TYPE IF EXISTS approval_status")
    op.execute("DROP TYPE IF EXISTS approval_queue")
    op.execute("DROP TYPE IF EXISTS payment_method")
    op.execute("DROP TYPE IF EXISTS severity_band")
    op.execute("DROP TYPE IF EXISTS audit_action")
    op.execute("DROP TYPE IF EXISTS audit_entity_type")
    op.execute("DROP TYPE IF EXISTS audit_actor_type")
