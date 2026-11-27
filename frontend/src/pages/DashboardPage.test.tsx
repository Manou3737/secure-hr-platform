import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuth } from '../auth/useAuth'
import { getDashboard } from '../api/dashboardService'
import { getDepartments } from '../api/departmentService'
import DashboardPage from './DashboardPage'

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
const dashboardData: DashboardResponse = {
  workforce: {
    headcount: {
      total: 120,
      active_accounts: 110,
      inactive_accounts: 10,
    },
    departments: {
      total: 3,
      distribution: [],
    },
    positions: {
      total: 5,
      distribution: [],
    },
    roles: [],
    hires: {
      this_month: 4,
      this_year: 15,
    },
    as_of: '2026-11-22',
  },
  compliance: {
    as_of: '2026-11-22',
    headcount: 120,
    profiles: {
      complete: 100,
      incomplete: 20,
      completion_rate: 83.33,
      incomplete_details: [],
    },
    documents: {
      compliant_employees: 90,
      employees_missing_required_documents: 30,
      compliance_rate: 75,
      missing_documents_details: [],
      expired_count: 5,
      expired_details: [],
      expiring_soon_count: 8,
      expiring_soon_details: [],
      recently_uploaded_count: 0,
      recently_uploaded_details: [],
    },
  },
  onboarding: {
    journeys: {
      total: 10,
      pending: 2,
      in_progress: 3,
      suspended: 1,
      completed: 3,
      cancelled: 1,
    },
    tasks: {
      total: 50,
      pending: 10,
      in_progress: 8,
      blocked: 2,
      completed: 25,
      cancelled: 1,
      overdue: 4,
      overdue_details: [],
      low_priority: 10,
      medium_priority: 20,
      high_priority: 15,
      urgent_priority: 5,
    },
    progress: {
      total_eligible_tasks: 45,
      completed_tasks: 25,
      percentage: 55.56,
    },
    as_of: '2026-11-22',
  },
  operations: {
    as_of: '2026-11-22',
    period_days: 7,
    workflows: {
      total: 30,
      success: 25,
      failure: 2,
      denied: 3,
    },
    notifications: {
      failed: 2,
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
      total_events: 40,
      login_success: 30,
      login_failed: 10,
    },
    detections: {
      brute_force: 2,
      suspicious_ip: 1,
      unauthorized_access: 3,
      privilege_escalation: 0,
    },
    sources: {
      distinct_ips: 5,
      distinct_users: 12,
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
      total_entries: 100,
      general_audit_entries: 60,
      document_access_entries: 25,
      workflow_entries: 15,
    },
    general_audit: {
      distribution: [],
    },
    document_access: {
      distribution: [],
      access_denied: 3,
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
      incomplete_profiles: 20,
      employees_missing_required_documents: 30,
      expired_documents: 5,
      documents_expiring_soon: 8,
    },
    document_lifecycle: {
      pending_scan: 3,
      pending_review: 4,
      quarantined: 1,
      rejected: 2,
      verified: 50,
      archived: 10,
    },
    security: {
      brute_force: 2,
      suspicious_ip: 1,
      unauthorized_access: 3,
      privilege_escalation: 0,
    },
  },
  recruitment: {
    as_of: '2026-11-22',
    period_days: 7,
    job_postings: {
      total: 8,
      by_status: [
        { status: 'OPEN', count: 5 },
        { status: 'CLOSED', count: 2 },
        { status: 'DRAFT', count: 1 },
      ],
    },
    applications: {
      total: 40,
      by_status: [],
      received_in_period: 12,
      hired_in_period: 2,
    },
    daily_activity: [],
  },
}

function renderDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <DashboardPage />
    </QueryClientProvider>,
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(useAuth).mockReturnValue({
      user: hrUser,
    } as ReturnType<typeof useAuth>)

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

  it('displays dashboard statistics from the API', async () => {
    vi.mocked(getDashboard).mockResolvedValue(dashboardData)

    renderDashboard()

    expect(await screen.findByText('120')).toBeInTheDocument()
    expect(screen.getByText('110')).toBeInTheDocument()

    const openPositionsCard = screen
      .getByText('Open Positions')
      .closest('article')

    expect(openPositionsCard).not.toBeNull()
    expect(within(openPositionsCard as HTMLElement).getByText('5')).toBeInTheDocument()

    expect(screen.getByText('7')).toBeInTheDocument()

    // Workforce overview
    expect(screen.getByText('Hires this month')).toBeInTheDocument()
    expect(screen.getByText('Hires this year')).toBeInTheDocument()
    expect(screen.getByText('Employees by department')).toBeInTheDocument()
    expect(screen.getByText('Employees by role')).toBeInTheDocument()

    expect(getDashboard).toHaveBeenCalledTimes(1)
  })

  it('displays a loading state', () => {
    vi.mocked(getDashboard).mockReturnValue(
      new Promise(() => {}),
    )

    renderDashboard()

    expect(
      screen.getByText('Loading dashboard metrics...'),
    ).toBeInTheDocument()
  })

  it('displays a safe error message when the API request fails', async () => {
    const technicalError =
      'Request failed with status code 500: internal database details'

    vi.mocked(getDashboard).mockRejectedValue(
      new Error(technicalError),
    )

    renderDashboard()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to load dashboard metrics. Please try again.',
    )

    expect(screen.queryByText(technicalError)).not.toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: 'Try again' }),
    ).toBeInTheDocument()
  })

  it('does not request dashboard metrics for employees', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: employeeUser,
    } as ReturnType<typeof useAuth>)

    renderDashboard()

    expect(
      screen.getByText(
        'Your account does not have access to HR dashboard metrics.',
      ),
    ).toBeInTheDocument()

    expect(getDashboard).not.toHaveBeenCalled()
  })

  it('requests dashboard metrics for the selected period', async () => {
    vi.mocked(getDashboard).mockResolvedValue(dashboardData)

    renderDashboard()

    await screen.findByText('120')

    fireEvent.change(
      screen.getByLabelText('Filter by period'),
      { target: { value: '30' } },
    )

    await waitFor(() => {
      expect(getDashboard).toHaveBeenLastCalledWith({
        days: 30,
      })
    })
  })

  it('requests dashboard metrics for the selected department', async () => {
    vi.mocked(getDashboard).mockResolvedValue(dashboardData)

    renderDashboard()

    await screen.findByText('120')
    await screen.findByRole('option', { name: 'Finance' })

    fireEvent.change(
      screen.getByLabelText('Filter by department'),
      { target: { value: '4' } },
    )

    await waitFor(() => {
      expect(getDashboard).toHaveBeenLastCalledWith({
        days: 7,
        department_id: 4,
      })
    })
  })

  it('keeps global department access for SUPER_ADMIN', async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: {
        ...hrUser,
        role: 'SUPER_ADMIN',
      },
    } as ReturnType<typeof useAuth>)

    vi.mocked(getDashboard).mockResolvedValue(dashboardData)

    renderDashboard()

    await screen.findByText('120')

    expect(
      screen.getByRole('combobox', {
        name: 'Filter by department',
      }),
    ).toBeInTheDocument()

    expect(getDashboard).toHaveBeenCalledWith({
      days: 7,
    })
  })

  it('does not expose a department filter to HR_MANAGER', async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: hrManagerUser,
    } as ReturnType<typeof useAuth>)

    vi.mocked(getDashboard).mockResolvedValue(dashboardData)

    renderDashboard()

    await screen.findByText('120')

    expect(
      screen.queryByLabelText('Filter by department'),
    ).not.toBeInTheDocument()

    expect(getDepartments).not.toHaveBeenCalled()

    fireEvent.change(
      screen.getByLabelText('Filter by period'),
      { target: { value: '30' } },
    )

    await waitFor(() => {
      expect(getDashboard).toHaveBeenLastCalledWith({
        days: 30,
      })
    })
  })
})
