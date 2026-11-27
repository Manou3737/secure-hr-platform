import { beforeEach, describe, expect, it, vi } from 'vitest'

import api from './client'
import {
  assignTask,
  getTaskById,
  getTasks,
  transitionTask,
} from './taskService'

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

const task = {
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

describe('taskService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches tasks with default pagination', async () => {
    const responseData = {
      count: 1,
      next: null,
      previous: null,
      results: [task],
    }

    vi.mocked(api.get).mockResolvedValue({
      data: responseData,
    } as never)

    const result = await getTasks()

    expect(api.get).toHaveBeenCalledWith(
      '/employees/onboarding/tasks/',
      {
        params: {
          page: 1,
          page_size: 20,
        },
      },
    )

    expect(result).toEqual(responseData)
  })

  it('fetches a task by UUID', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: task,
    } as never)

    const result = await getTaskById(task.id)

    expect(api.get).toHaveBeenCalledWith(
      `/employees/onboarding/tasks/${task.id}/`,
    )

    expect(result).toEqual(task)
  })

  it('sends custom pagination and filters', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        count: 0,
        next: null,
        previous: null,
        results: [],
      },
    } as never)

    await getTasks({
      page: 2,
      page_size: 10,
      status: 'IN_PROGRESS',
      priority: 'HIGH',
      assigned_to: 12,
    })

    expect(api.get).toHaveBeenCalledWith(
      '/employees/onboarding/tasks/',
      {
        params: {
          page: 2,
          page_size: 10,
          status: 'IN_PROGRESS',
          priority: 'HIGH',
          assigned_to: 12,
        },
      },
    )
  })

  it('assigns a task to a user', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: task,
    } as never)

    const result = await assignTask(task.id, 15)

    expect(api.post).toHaveBeenCalledWith(
      `/employees/onboarding/tasks/${task.id}/assign/`,
      {
        assigned_to_id: 15,
      },
    )

    expect(result).toEqual(task)
  })

  it('transitions a task to a new status', async () => {
    const updatedTask = {
      ...task,
      status: 'IN_PROGRESS',
    }

    vi.mocked(api.post).mockResolvedValue({
      data: updatedTask,
    } as never)

    const result = await transitionTask(
      task.id,
      'IN_PROGRESS',
    )

    expect(api.post).toHaveBeenCalledWith(
      `/employees/onboarding/tasks/${task.id}/transition/`,
      {
        target_status: 'IN_PROGRESS',
      },
    )

    expect(result).toEqual(updatedTask)
  })
})
