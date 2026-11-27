import api from './client'
import type { PaginatedResponse } from './employeeService'

export type TaskStatus =
  | 'PENDING'
  | 'IN_PROGRESS'
  | 'BLOCKED'
  | 'COMPLETED'
  | 'CANCELLED'

export type TaskPriority =
  | 'LOW'
  | 'MEDIUM'
  | 'HIGH'
  | 'URGENT'

export interface OnboardingTask {
  id: string
  journey: string
  activity_template: number
  title: string
  description: string
  status: TaskStatus
  priority: TaskPriority
  assigned_to: number | null
  due_date: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface TaskFilters {
  status?: TaskStatus
  priority?: TaskPriority
  assigned_to?: number
  ordering?: string
}

export interface TaskListParams extends TaskFilters {
  page?: number
  page_size?: number
}

export async function getTasks(
  params: TaskListParams = {},
): Promise<PaginatedResponse<OnboardingTask>> {
  const response = await api.get<PaginatedResponse<OnboardingTask>>(
    '/employees/onboarding/tasks/',
    {
      params: {
        ...params,
        page: params.page ?? 1,
        page_size: params.page_size ?? 20,
      },
    },
  )

  return response.data
}

export async function getTaskById(
  id: string,
): Promise<OnboardingTask> {
  const response = await api.get<OnboardingTask>(
    `/employees/onboarding/tasks/${id}/`,
  )

  return response.data
}

export async function assignTask(
  id: string,
  assignedToId: number,
): Promise<OnboardingTask> {
  const response = await api.post<OnboardingTask>(
    `/employees/onboarding/tasks/${id}/assign/`,
    { assigned_to_id: assignedToId },
  )

  return response.data
}

export async function transitionTask(
  id: string,
  targetStatus: TaskStatus,
): Promise<OnboardingTask> {
  const response = await api.post<OnboardingTask>(
    `/employees/onboarding/tasks/${id}/transition/`,
    { target_status: targetStatus },
  )

  return response.data
}
