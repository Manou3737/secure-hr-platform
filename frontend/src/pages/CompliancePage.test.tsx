import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { getDashboard } from '../api/dashboardService'
import { getDepartments } from '../api/departmentService'
import CompliancePage from './CompliancePage'

import type { AuthUser } from '../auth/authService'
import type { DashboardResponse } from '../api/dashboardService'

vi.mock('../auth/useAuth', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../api/dashboardService', () => ({
  getDashboard: vi.fn(),
}))

vi.mock('../api/departmentService', () => ({
  getDepartments: vi.fn(),
}))

const hrUser: AuthUser = {
  id: 1,
  email: 'admin@example.com',
  name: 'HR Admin',
  role: 'HR_ADMIN',
  email_verified: true,
  is_active: true,
}

const employeeUser: AuthUser = {
  ...hrUser,
  role: 'EMPLOYEE',
}

const hrManagerUser: AuthUser = {
  ...hrUser,
  id: 2,
  email: 'manager@example.com',
  name: 'HR Manager',
  role: 'HR_MANAGER',
}

const complianceDashboard: DashboardResponse = {
  workforce: {
    headcount: {
      total: 3,
      active_accounts: 3,
      inactive_accounts: 0,
    },
    departments: {
      total: 2,
      distribution: [],
    },
    positions: {
      total: 2,
      distribution: [],
    },
    roles: [],
    hires: {
      this_month: 1,
      this_year: 2,
    },
    as_of: '2026-11-22',
  },
  compliance: {
    as_of: '2026-11-22',
    headcount: 3,
    profiles: {
      complete: 2,
      incomplete: 1,
      completion_rate: 66.7,
      incomplete_details: [
        {
          id: 10,
          employee_id: 100,
          user__name: 'Alice Martin',
          department__name: 'Engineering',
          position__title: 'Developer',
        },
      ],
    },
    documents: {
      compliant_employees: 2,
      employees_missing_required_documents: 1,
      compliance_rate: 66.7,
      missing_documents_details: [
        {
          employee_id: 100,
          employee_name: 'Alice Martin',
          missing_document_types: ['ID Card', 'Work Authorization'],
        },
      ],
      expired_count: 1,
      expired_details: [
        {
          id: 'doc-expired-1',
          employee_id: 100,
          employee__user__name: 'Alice Martin',
          document_type: 'Passport',
          expires_at: '2026-10-15',
        },
      ],
      expiring_soon_count: 1,
      expiring_soon_details: [
        {
          id: 'doc-expiring-1',
          employee_id: 101,
          employee__user__name: 'Bob Smith',
          document_type: 'Work Permit',
          expires_at: '2026-12-01',
        },
      ],
      recently_uploaded_count: 0,
      recently_uploaded_details: [],
    },
  },
  onboarding: {
    journeys: {
      total: 0,
      pending: 0,
      in_progress: 0,
      suspended: 0,
      completed: 0,
      cancelled: 0,
    },
    tasks: {
      total: 0,
      pending: 0,
      in_progress: 0,
      blocked: 0,
      completed: 0,
      cancelled: 0,
      overdue: 0,
      overdue_details: [],
      low_priority: 0,
      medium_priority: 0,
      high_priority: 0,
      urgent_priority: 0,
    },
    progress: {
      total_eligible_tasks: 0,
      completed_tasks: 0,
      percentage: 0,
    },
    as_of: '2026-11-22',
  },
  operations: {
    as_of: '2026-11-22',
    period_days: 7,
    workflows: {
      total: 0,
      success: 0,
      failure: 0,
      denied: 0,
    },
    notifications: {
      failed: 0,
      by_type: [],
    },
    events: {
      distribution: [],
    },
    daily_activity: [],
  },
  security: {
    as_of: '2026-11-22',
    period_days: 7,
    overview: {
      total_events: 0,
      login_success: 0,
      login_failed: 0,
    },
    detections: {
      brute_force: 0,
      suspicious_ip: 0,
      unauthorized_access: 0,
      privilege_escalation: 0,
    },
    sources: {
      distinct_ips: 0,
      distinct_users: 0,
    },
    events: {
      distribution: [],
    },
    daily_activity: [],
    recent_events: [],
  },
  audit: {
    as_of: '2026-11-22',
    period_days: 7,
    overview: {
      total_entries: 0,
      general_audit_entries: 0,
      document_access_entries: 0,
      workflow_entries: 0,
    },
    general_audit: {
      distribution: [],
    },
    document_access: {
      distribution: [],
      access_denied: 0,
    },
    workflows: {
      distribution: [],
      outcomes: {},
    },
    daily_activity: {
      general_audit: [],
      document_access: [],
      workflow: [],
    },
    recent_events: {
      general_audit: [],
      document_access: [],
      workflow: [],
    },
  },
  risk: {
    as_of: '2026-11-22',
    compliance: {
      incomplete_profiles: 1,
      employees_missing_required_documents: 1,
      expired_documents: 1,
      documents_expiring_soon: 1,
    },
    document_lifecycle: {
      pending_scan: 0,
      pending_review: 0,
      quarantined: 0,
      rejected: 0,
      verified: 0,
      archived: 0,
    },
    security: {
      brute_force: 0,
      suspicious_ip: 0,
      unauthorized_access: 0,
      privilege_escalation: 0,
    },
  },
  recruitment: {
    as_of: '2026-11-22',
    period_days: 7,
    job_postings: {
      total: 0,
      by_status: [],
    },
    applications: {
      total: 0,
      by_status: [],
      received_in_period: 0,
      hired_in_period: 0,
    },
    daily_activity: [],
  },
}

function renderCompliance() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <CompliancePage />
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('CompliancePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(useAuth).mockReturnValue({
      user: hrUser,
    } as ReturnType<typeof useAuth>)

    vi.mocked(getDashboard).mockResolvedValue(complianceDashboard)

    vi.mocked(getDepartments).mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [
        {
          id: 2,
          name: 'Engineering',
          code: 'ENG',
          description: 'Engineering department',
        },
        {
          id: 4,
          name: 'Finance',
          code: 'FIN',
          description: 'Finance department',
        },
      ],
    })
  })

  it('displays the four compliance indicators', async () => {
    renderCompliance()

    const metrics = await screen.findByRole('region', {
      name: 'Compliance metrics',
    })

    const profileCard = within(metrics)
      .getByText('Profile completion')
      .closest('article')

    const documentCard = within(metrics)
      .getByText('Document compliance')
      .closest('article')

    const expiredCard = within(metrics)
      .getByText('Expired documents')
      .closest('article')

    const expiringCard = within(metrics)
      .getByText('Expiring soon')
      .closest('article')

    expect(within(profileCard as HTMLElement).getByText('66.7%')).toBeInTheDocument()
    expect(within(documentCard as HTMLElement).getByText('66.7%')).toBeInTheDocument()
    expect(within(expiredCard as HTMLElement).getByText('1')).toBeInTheDocument()
    expect(within(expiringCard as HTMLElement).getByText('1')).toBeInTheDocument()
  })

  it('displays expired documents', async () => {
    renderCompliance()

    const section = await screen.findByRole('region', {
      name: 'Expired documents',
    })

    expect(within(section).getByText('Passport')).toBeInTheDocument()
    expect(within(section).getByText('Alice Martin')).toBeInTheDocument()
    expect(
      within(section).getByRole('link', { name: 'Passport' }),
    ).toHaveAttribute('href', '/documents/doc-expired-1')
  })

  it('displays documents expiring soon', async () => {
    renderCompliance()

    expect(await screen.findByText('Work Permit')).toBeInTheDocument()
    expect(screen.getByText('Bob Smith')).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Work Permit' }),
    ).toHaveAttribute('href', '/documents/doc-expiring-1')
  })

  it('displays employees with missing required documents', async () => {
    renderCompliance()

    expect(await screen.findByText('ID Card, Work Authorization')).toBeInTheDocument()
  })

  it('displays incomplete employee profiles', async () => {
    renderCompliance()

    const section = await screen.findByRole('region', {
      name: 'Incomplete employee profiles',
    })

    expect(within(section).getByText('Alice Martin')).toBeInTheDocument()
    expect(within(section).getByText('Engineering')).toBeInTheDocument()
    expect(within(section).getByText('Developer')).toBeInTheDocument()
  })

  it('displays a loading state', () => {
    vi.mocked(getDashboard).mockReturnValue(new Promise(() => {}))

    renderCompliance()

    expect(
      screen.getByText('Loading compliance data...'),
    ).toBeInTheDocument()
  })

  it('displays a safe error message when the API request fails', async () => {
    const technicalError = '500: internal database details'

    vi.mocked(getDashboard).mockRejectedValue(new Error(technicalError))

    renderCompliance()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to load compliance data.',
    )

    expect(screen.queryByText(technicalError)).not.toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: 'Retry' }),
    ).toBeInTheDocument()
  })

  it('does not request compliance metrics for employees', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: employeeUser,
    } as ReturnType<typeof useAuth>)

    renderCompliance()

    expect(
      screen.getByText(
        'Your account does not have access to HR compliance metrics.',
      ),
    ).toBeInTheDocument()

    expect(getDashboard).not.toHaveBeenCalled()
    expect(getDepartments).not.toHaveBeenCalled()
  })

  it('requests compliance metrics for the selected department', async () => {
    renderCompliance()

    await screen.findByText('Passport')

    fireEvent.change(
      screen.getByLabelText('Department'),
      { target: { value: '4' } },
    )

    await waitFor(() => {
    expect(getDashboard).toHaveBeenLastCalledWith({
      department_id: 4,
      expiring_within_days: 30,
    })
    })
  })

  it('keeps the department filter available for SUPER_ADMIN', async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: {
        ...hrUser,
        role: 'SUPER_ADMIN',
      },
    } as ReturnType<typeof useAuth>)

    renderCompliance()

    await screen.findByText('Passport')

    expect(
      screen.getByRole('combobox', { name: 'Department' }),
    ).toBeInTheDocument()

    expect(getDashboard).toHaveBeenCalledWith({
      expiring_within_days: 30,
    })
  })

  it('does not expose a department filter to HR_MANAGER', async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: hrManagerUser,
    } as ReturnType<typeof useAuth>)

    renderCompliance()

    await screen.findByText('Passport')

    expect(
      screen.queryByLabelText('Department'),
    ).not.toBeInTheDocument()

    expect(getDepartments).not.toHaveBeenCalled()

    expect(getDashboard).toHaveBeenCalledWith({
      expiring_within_days: 30,
    })
  })
})
