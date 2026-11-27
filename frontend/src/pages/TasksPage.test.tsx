
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { getTasks, transitionTask } from '../api/taskService'
import type { OnboardingTask } from '../api/taskService'
import type { AuthUser } from '../auth/authService'
import TasksPage from './TasksPage'

vi.mock('../auth/useAuth', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../api/taskService', () => ({
  getTasks: vi.fn(),
  transitionTask: vi.fn(),
}))

const task: OnboardingTask = {
  id: '550e8400-e29b-41d4-a716-446655440000',
  journey: '650e8400-e29b-41d4-a716-446655440000',
  activity_template: 3,
  title: 'Complete employee orientation',
  description: 'Review onboarding materials',
  status: 'PENDING',
  priority: 'HIGH',
  assigned_to: 12,
  due_date: '2026-12-01',
  started_at: null,
  completed_at: null,
  created_at: '2026-11-20T10:00:00Z',
  updated_at: '2026-11-20T10:00:00Z',
}

function createUser(role: AuthUser['role']): AuthUser {
  return {
    id: 1,
    email: 'test@example.com',
    name: 'Test User',
    role,
    email_verified: true,
    is_active: true,
  }
}

function renderTasksPage(role: AuthUser['role']) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  })

  vi.mocked(useAuth).mockReturnValue({
    user: createUser(role),
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <TasksPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TasksPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(getTasks).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [task],
    })

    vi.mocked(transitionTask).mockResolvedValue({
      ...task,
      status: 'IN_PROGRESS',
    })
  })

  it('displays tasks returned by the API', async () => {
    renderTasksPage('EMPLOYEE')

    expect(
      await screen.findByText('Complete employee orientation'),
    ).toBeInTheDocument()

    expect(screen.getByText('Review onboarding materials')).toBeInTheDocument()
    expect(screen.getByText('High')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('11/30/2026')).toBeInTheDocument()

    expect(getTasks).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
    })
  })

  it('links each task title to its detail page', async () => {
    renderTasksPage('EMPLOYEE')

    const taskLink = await screen.findByRole('link', {
      name: 'Complete employee orientation',
    })

    expect(taskLink).toHaveAttribute(
      'href',
      `/tasks/${task.id}`,
    )
  })

  it('displays a loading state', () => {
    vi.mocked(getTasks).mockReturnValue(new Promise(() => {}))

    renderTasksPage('EMPLOYEE')

    expect(
      screen.getByText('Loading onboarding tasks...'),
    ).toBeInTheDocument()
  })

  it('displays a safe error message when loading tasks fails', async () => {
    vi.mocked(getTasks).mockRejectedValue(
      new Error('Internal database details'),
    )

    renderTasksPage('EMPLOYEE')

    expect(
      await screen.findByText('Unable to load onboarding tasks.'),
    ).toBeInTheDocument()

    expect(
      screen.queryByText('Internal database details'),
    ).not.toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: 'Try again' }),
    ).toBeInTheDocument()
  })

  it('does not allow employees to change task status', async () => {
    renderTasksPage('EMPLOYEE')

    await screen.findByText('Complete employee orientation')

    expect(
      screen.queryByRole('button', { name: 'In Progress' }),
    ).not.toBeInTheDocument()

    expect(
      screen.queryByRole('button', { name: 'Cancelled' }),
    ).not.toBeInTheDocument()
  })

  it.each(['HR_MANAGER', 'HR_ADMIN', 'SUPER_ADMIN'] as const)(
    '%s can request an allowed task transition',
    async (role) => {
      renderTasksPage(role)

      await screen.findByText('Complete employee orientation')

      fireEvent.click(
        screen.getByRole('button', { name: 'In Progress' }),
      )

      expect(
        screen.getByRole('alertdialog'),
      ).toBeInTheDocument()

      fireEvent.click(
        screen.getByRole('button', { name: 'Confirm' }),
      )

      await waitFor(() => {
        expect(transitionTask).toHaveBeenCalledWith(
          task.id,
          'IN_PROGRESS',
        )
      })
    },
  )

  it('does not call the transition API before confirmation', async () => {
    renderTasksPage('HR_ADMIN')

    await screen.findByText('Complete employee orientation')

    fireEvent.click(
      screen.getByRole('button', { name: 'In Progress' }),
    )

    expect(transitionTask).not.toHaveBeenCalled()

    fireEvent.click(
      screen.getByRole('button', { name: 'Cancel' }),
    )

    expect(transitionTask).not.toHaveBeenCalled()
  })

  it('does not expose invalid transitions for a pending task', async () => {
    renderTasksPage('HR_ADMIN')

    await screen.findByText('Complete employee orientation')

    expect(
      screen.queryByRole('button', { name: 'Completed' }),
    ).not.toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: 'In Progress' }),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: 'Cancelled' }),
    ).toBeInTheDocument()
  })

  it('displays an empty state when no tasks are returned', async () => {
    vi.mocked(getTasks).mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })

    renderTasksPage('EMPLOYEE')

    expect(
      await screen.findByText('No onboarding tasks found.'),
    ).toBeInTheDocument()
  })
})
