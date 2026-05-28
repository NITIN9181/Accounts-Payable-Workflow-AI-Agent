/**
 * Role-based access control hook.
 *
 * Roles and their approval authority:
 *   AP_CLERK  – invoices up to $5,000 (department threshold)
 *   MANAGER   – invoices up to $25,000 (manager threshold)
 *   CFO       – invoices above $25,000 / full system access
 */
import { useAuth } from '../context/AuthContext'

export type Role = 'AP_CLERK' | 'MANAGER' | 'CFO'

// Dollar thresholds that mirror the backend defaults
const CLERK_THRESHOLD = 5_000
const MANAGER_THRESHOLD = 25_000

export function useRole() {
  const { user } = useAuth()
  const role = (user?.role ?? null) as Role | null

  const isClerk = role === 'AP_CLERK'
  const isManager = role === 'MANAGER'
  const isCFO = role === 'CFO'

  /** True for Manager and CFO */
  const isManagerOrAbove = isManager || isCFO

  /** True only for CFO */
  const isCFOOnly = isCFO

  /**
   * Returns true if this role is allowed to approve an invoice of the given amount.
   * Clerks handle < $5k, Managers handle $5k–$25k, CFO handles > $25k.
   */
  function canApprove(amount: number): boolean {
    if (isCFO) return true
    if (isManager) return amount <= MANAGER_THRESHOLD
    if (isClerk) return amount <= CLERK_THRESHOLD
    return false
  }

  /**
   * Returns the queue name this role should be watching.
   */
  function myQueue(): string {
    if (isCFO) return 'CFO_ESCALATION_QUEUE'
    if (isManager) return 'MANAGER_QUEUE'
    return 'AP_CLERK_QUEUE'
  }

  /**
   * Human-readable label for the role.
   */
  function roleLabel(): string {
    if (isCFO) return 'CFO'
    if (isManager) return 'Manager'
    if (isClerk) return 'AP Clerk'
    return 'Unknown'
  }

  return {
    role,
    isClerk,
    isManager,
    isCFO,
    isManagerOrAbove,
    isCFOOnly,
    canApprove,
    myQueue,
    roleLabel,
    CLERK_THRESHOLD,
    MANAGER_THRESHOLD,
  }
}
