/**
 * Invoice types
 */
export interface Invoice {
  invoice_id: string
  vendor_key: string
  vendor_name: string
  invoice_number: string
  total_amount: number
  total_amount_usd: number
  tax_amount?: number
  invoice_date: string
  due_date: string
  po_reference?: string
  currency_code: string
  fx_rate?: number
  stale_fx_rate: boolean
  file_hash: string
  file_path?: string
  ingestion_source: 'email' | 'upload' | 'webhook' | 'manual'
  status: InvoiceStatus
  received_at: string
  ocr_completed_at?: string
  matching_completed_at?: string
  anomaly_completed_at?: string
  approved_at?: string
  paid_at?: string
  demo_mode: boolean
  created_at: string
  updated_at: string
}

export type InvoiceStatus =
  | 'PENDING_OCR'
  | 'PENDING_MANUAL_REVIEW'
  | 'PENDING_APPROVAL'
  | 'APPROVED'
  | 'SCHEDULED'
  | 'PAID'
  | 'REJECTED'
  | 'HELD'
  | 'OCR_FAILED'
  | 'INGESTION_FAILED'

/**
 * Exception types
 */
export interface InvoiceException {
  exception_id: string
  invoice_id: string
  exception_type: ExceptionType
  severity: number
  severity_band: SeverityBand
  details_json: Record<string, unknown>
  llm_explanation?: string
  llm_explanation_fallback: boolean
  llm_explanation_ready: boolean
  resolved: boolean
  created_at: string
}

export type ExceptionType =
  | 'DUPLICATE_EXACT'
  | 'DUPLICATE_FUZZY'
  | 'PO_MATCHED'
  | 'PO_MISMATCH'
  | 'PO_MISSING'
  | 'PARTIAL_RECEIPT'
  | 'RECEIPT_MISSING'
  | 'INCOMPLETE_DATA'
  | 'ANOMALY_ZSCORE'
  | 'ANOMALY_ISOLATION_FOREST'

export type SeverityBand = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'

/**
 * Approval types
 */
export interface Approval {
  approval_id: string
  invoice_id: string
  approver_id?: string
  approver_role: 'AP_CLERK' | 'MANAGER' | 'CFO'
  approval_queue: string
  status: ApprovalStatus
  sla_deadline: string
  sla_violated: boolean
  notes?: string
  created_at: string
  completed_at?: string
}

export type ApprovalStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'ESCALATED'

/**
 * Payment types
 */
export interface Payment {
  payment_id: string
  invoice_id: string
  scheduled_payment_date: string
  payment_method: 'ACH' | 'WIRE' | 'CHECK'
  payment_amount: number
  discount_captured?: number
  status: PaymentStatus
  created_at: string
  executed_at?: string
}

export type PaymentStatus = 'SCHEDULED' | 'EXECUTED' | 'FAILED'

/**
 * Vendor Baseline types
 */
export interface VendorBaseline {
  vendor_key: string
  vendor_name: string
  txn_count_total: number
  mean_invoice_amount_30d: number
  std_invoice_amount_30d: number
  p95_invoice_amount_90d: number
  avg_days_to_pay_90d: number
  auto_approve_max_amount: number
  auto_approve_max_zscore: number
  preferred_payment_method: 'ACH' | 'WIRE' | 'CHECK'
  created_at: string
  updated_at: string
}

/**
 * Audit Log types
 */
export interface AuditLog {
  log_id: string
  actor_id?: string
  actor_type: 'ANALYST' | 'SYSTEM' | 'API' | 'VENDOR'
  action_type: string
  entity_type: 'INVOICE' | 'EXCEPTION' | 'APPROVAL' | 'PAYMENT'
  entity_id: string
  before_state?: Record<string, unknown>
  after_state?: Record<string, unknown>
  ip_address?: string
  user_agent?: string
  created_at: string
}

/**
 * WebSocket Event types
 */
export interface WebSocketEvent {
  type: 'EXCEPTION_CREATED' | 'EXPLANATION_READY' | 'INVOICE_STATUS_CHANGED' | 'CONNECTION_ACK'
  payload: Record<string, unknown>
  timestamp: string
}

export interface ExceptionCreatedEvent extends WebSocketEvent {
  type: 'EXCEPTION_CREATED'
  payload: {
    exception_id: string
    invoice_id: string
    vendor_name: string
    total_amount: number
    final_severity: number
    severity_band: SeverityBand
    exception_type: ExceptionType
    llm_explanation?: string
    llm_explanation_ready: boolean
  }
}

export interface ExplanationReadyEvent extends WebSocketEvent {
  type: 'EXPLANATION_READY'
  payload: {
    exception_id: string
    llm_explanation: string
    fallback: boolean
  }
}

export interface InvoiceStatusChangedEvent extends WebSocketEvent {
  type: 'INVOICE_STATUS_CHANGED'
  payload: {
    invoice_id: string
    old_status: InvoiceStatus
    new_status: InvoiceStatus
    actor_id?: string
    timestamp: string
  }
}
