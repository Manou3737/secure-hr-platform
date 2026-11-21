import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuth } from '../auth/useAuth'
import { getDashboard } from '../api/dashboardService'
import DashboardPage from './DashboardPage'

import type { AuthUser } from '../auth/authService'
import type { DashboardResponse } from '../api/dashboardService'

vi.mock('../auth/useAuth', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../api/dashboardService', () => ({
  getDashboard: vi.fn(),
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

const dashboardData: DashboardResponse = {
  workforce: {
    headcount: {
      total: 120,
      active_accounts: 110,
      inactive_accounts: 10,
    },
  },
  recruitment: {
    job_postings: {
      total: 8,
      by_status: [
        { status: 'OPEN', count: 5 },
        { status: 'CLOSED', count: 2 },
        { status: 'DRAFT', count: 1 },
      ],
    },
  },
  risk: {
    document_lifecycle: {
      pending_scan: 3,
      pending_review: 4,
      quarantined: 1,
      rejected: 2,
      verified: 50,
      archived: 10,
    },
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
  })

  it('displays dashboard statistics from the API', async () => {
    vi.mocked(getDashboard).mockResolvedValue(dashboardData)

    renderDashboard()

    expect(await screen.findByText('120')).toBeInTheDocument()
    expect(screen.getByText('110')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()

    expect(getDashboard).toHaveBeenCalledTimes(1)
  })

  it('displays a loading state', () => {
    vi.mocked(getDashboard).mockReturnValue(
      new Promise(() => {}),
    )

    renderDashboard()

    expect(screen.getByRole('status')).toHaveTextContent(
      'Loading dashboard metrics...',
    )
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
})
