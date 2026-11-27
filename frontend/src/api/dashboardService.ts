import api from './client'

// ─────────────────────────────────────────────
// Shared types
// ─────────────────────────────────────────────

export interface CountDistribution {
  count: number
  [key: string]: string | number
}

export interface DailyActivity {
  count: number
  [key: string]: string | number
}

// ─────────────────────────────────────────────
// Workforce
// ─────────────────────────────────────────────

export interface WorkforceMetrics {
  headcount: {
    total: number
    active_accounts: number
    inactive_accounts: number
  }
  departments: {
    total: number
    distribution: Array<{
      department_id: number
      department__name: string
      department__code: string
      employee_count: number
    }>
  }
  positions: {
    total: number
    distribution: Array<{
      position_id: number
      position__title: string
      department__name: string
      employee_count: number
    }>
  }
  roles: Array<{
    user__role: string
    employee_count: number
  }>
  hires: {
    this_month: number
    this_year: number
  }
  as_of: string
}

// ─────────────────────────────────────────────
// Compliance
// ─────────────────────────────────────────────

export interface ComplianceMetrics {
  as_of: string
  headcount: number
  profiles: {
    complete: number
    incomplete: number
    completion_rate: number
    incomplete_details: Array<{
      id: number
      employee_id: number
      user__name: string
      department__name: string
      position__title: string
    }>
  }
  documents: {
    compliant_employees: number
    employees_missing_required_documents: number
    compliance_rate: number
    missing_documents_details: Array<{
      employee_id: number
      employee_name: string
      missing_document_types: string[]
    }>
    expired_count: number
    expired_details: Array<{
      id: string
      employee_id: number
      employee__user__name: string
      document_type: string
      expires_at: string
    }>
    expiring_soon_count: number
    expiring_soon_details: Array<{
      id: string
      employee_id: number
      employee__user__name: string
      document_type: string
      expires_at: string
    }>
    recently_uploaded_count: number
    recently_uploaded_details: Array<{
      id: string
      employee_id: string
      employee__user__name: string
      document_type: string
      status: string
      uploaded_at: string
    }>
  }
}

// ─────────────────────────────────────────────
// Onboarding
// ─────────────────────────────────────────────

export interface OnboardingMetrics {
  journeys: {
    total: number
    pending: number
    in_progress: number
    suspended: number
    completed: number
    cancelled: number
  }
  tasks: {
    total: number
    pending: number
    in_progress: number
    blocked: number
    completed: number
    cancelled: number
    overdue: number
    overdue_details: Array<{
      id: string
      title: string
      due_date: string
      priority: string
      status: string
      employee_name: string
    }>
    low_priority: number
    medium_priority: number
    high_priority: number
    urgent_priority: number
  }
  progress: {
    total_eligible_tasks: number
    completed_tasks: number
    percentage: number
  }
  as_of: string
}

// ─────────────────────────────────────────────
// Operations
// ─────────────────────────────────────────────

export interface OperationsMetrics {
  as_of: string
  period_days: number
  workflows: {
    total: number
    success: number
    failure: number
    denied: number
  }
  notifications: {
    failed: number
    by_type: Array<{
      details__notification_type: string
      count: number
    }>
  }
  events: {
    distribution: Array<{
      event_type: string
      count: number
    }>
  }
  daily_activity: Array<{
    created_at__date: string
    count: number
  }>
}

// ─────────────────────────────────────────────
// Security
// ─────────────────────────────────────────────

export interface SecurityMetrics {
  as_of: string
  period_days: number
  overview: {
    total_events: number
    login_success: number
    login_failed: number
  }
  detections: {
    brute_force: number
    suspicious_ip: number
    unauthorized_access: number
    privilege_escalation: number
  }
  sources: {
    distinct_ips: number
    distinct_users: number
  }
  events: {
    distribution: Array<{
      event_type: string
      count: number
    }>
  }
  daily_activity: Array<{
    created_at__date: string
    count: number
  }>
  recent_events: Array<{
    id: number
    event_type: string
    ip_address: string | null
    request_path: string | null
    created_at: string
  }>
}

// ─────────────────────────────────────────────
// Audit
// ─────────────────────────────────────────────

export interface AuditMetrics {
  as_of: string
  period_days: number
  overview: {
    total_entries: number
    general_audit_entries: number
    document_access_entries: number
    workflow_entries: number
  }
  general_audit: {
    distribution: Array<{
      action: string
      count: number
    }>
  }
  document_access: {
    distribution: Array<{
      action: string
      count: number
    }>
    access_denied: number
  }
  workflows: {
    distribution: Array<{
      event_type: string
      count: number
    }>
    outcomes: Record<string, number>
  }
  daily_activity: {
    general_audit: Array<{
      created_at__date: string
      count: number
    }>
    document_access: Array<{
      created_at__date: string
      count: number
    }>
    workflow: Array<{
      created_at__date: string
      count: number
    }>
  }
  recent_events: {
    general_audit: Array<{
      id: number
      action: string
      user_id: number | null
      created_at: string
    }>
    document_access: Array<{
      id: number
      action: string
      user_id: number | null
      document_id: string | null
      created_at: string
    }>
    workflow: Array<{
      id: number
      event_type: string
      outcome: string
      actor_id: number | null
      created_at: string
    }>
  }
}

// ─────────────────────────────────────────────
// Risk
// ─────────────────────────────────────────────

export interface RiskMetrics {
  as_of: string
  compliance: {
    incomplete_profiles: number
    employees_missing_required_documents: number
    expired_documents: number
    documents_expiring_soon: number
  }
  document_lifecycle: {
    pending_scan: number
    pending_review: number
    quarantined: number
    rejected: number
    verified: number
    archived: number
  }
  security: {
    brute_force: number
    suspicious_ip: number
    unauthorized_access: number
    privilege_escalation: number
  }
}

// ─────────────────────────────────────────────
// Recruitment
// ─────────────────────────────────────────────

export interface RecruitmentMetrics {
  as_of: string
  period_days: number
  job_postings: {
    total: number
    by_status: Array<{
      status: string
      count: number
    }>
  }
  applications: {
    total: number
    by_status: Array<{
      status: string
      count: number
    }>
    received_in_period: number
    hired_in_period: number
  }
  daily_activity: Array<{
    applied_at__date: string
    count: number
  }>
}

// ─────────────────────────────────────────────
// Dashboard API response
// ─────────────────────────────────────────────

export interface DashboardResponse {
  workforce: WorkforceMetrics
  compliance: ComplianceMetrics
  onboarding: OnboardingMetrics
  operations: OperationsMetrics
  security: SecurityMetrics
  audit: AuditMetrics
  risk: RiskMetrics
  recruitment: RecruitmentMetrics
}

// ─────────────────────────────────────────────
// API service
// ─────────────────────────────────────────────

export interface DashboardFilters {
  department_id?: number
  site_id?: number
  expiring_within_days?: 7 | 30 | 60 | 90
  uploaded_within_days?: 7 | 30 | 60 | 90
  days?: number
  as_of?: string
  recent_limit?: number
}

export async function getDashboard(
  filters: DashboardFilters = {},
): Promise<DashboardResponse> {
  const response = await api.get<DashboardResponse>(
    '/employees/dashboard/',
    {
      params: filters,
    },
  )

  return response.data
}
