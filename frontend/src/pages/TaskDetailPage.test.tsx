import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import TaskDetailPage from './TaskDetailPage'
import { getTaskById } from '../api/taskService'

vi.mock('../api/taskService', () => ({
  getTaskById: vi.fn(),
}))

const taskId = '550e8400-e29b-41d4-a716-446655440000'

const mockTask = {
  id: taskId,
  journey: '650e8400-e29b-41d4-a716-446655440000',
  activity_template: 3,
  title: 'Complete employee orientation',
  description: 'Review onboarding materials',
  status: 'PENDING' as const,
  priority: 'HIGH' as const,
  assigned_to: 12,
  due_date: '2026-12-01',
  started_at: null,
  completed_at: null,
  created_at: '2026-11-20T10:00:00Z',
  updated_at: '2026-11-20T10:00:00Z',
}

function renderTaskDetail(path = `/tasks/${taskId}`) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/tasks/:id" element={<TaskDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TaskDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays task details returned by the API', async () => {
    vi.mocked(getTaskById).mockResolvedValue(mockTask)

    renderTaskDetail()

    expect(
      await screen.findByRole('heading', { name: 'Task details' }),
    ).toBeInTheDocument()

    expect(screen.getByText('Complete employee orientation')).toBeInTheDocument()
    expect(screen.getByText('Review onboarding materials')).toBeInTheDocument()
    expect(screen.getByText('Pending')).toBeInTheDocument()
    expect(screen.getByText('High')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('2026-12-01')).toBeInTheDocument()

    expect(getTaskById).toHaveBeenCalledWith(taskId)
  })

  it('does not call the API when the task ID is invalid', () => {
    renderTaskDetail('/tasks/not-a-valid-uuid')

    expect(screen.getByText('Invalid task ID.')).toBeInTheDocument()
    expect(getTaskById).not.toHaveBeenCalled()
  })

  it('displays a loading state while the API request is pending', () => {
    vi.mocked(getTaskById).mockImplementation(
      () => new Promise(() => {}),
    )

    renderTaskDetail()

    expect(screen.getByText('Loading task details...')).toBeInTheDocument()
  })

  it('displays a safe error when the API request fails', async () => {
    vi.mocked(getTaskById).mockRejectedValue(
      new Error('Sensitive backend error details'),
    )

    renderTaskDetail()

    expect(
      await screen.findByText(
        'Unable to load this task. It may not exist or you may not have permission to view it.',
      ),
    ).toBeInTheDocument()

    expect(
      screen.queryByText('Sensitive backend error details'),
    ).not.toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: 'Retry' }),
    ).toBeInTheDocument()
  })

  it('provides a link back to the tasks list', async () => {
    vi.mocked(getTaskById).mockResolvedValue(mockTask)

    renderTaskDetail()

    expect(
      await screen.findByRole('link', { name: /back to tasks/i }),
    ).toHaveAttribute('href', '/tasks')
  })
})
