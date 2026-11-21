import api from './client'

export interface EmployeeProfile {
  id: number
  user: number
  employee_id: string
  department: number
  position: number
  phone: string
  hire_date: string
  date_of_birth: string | null
  address: string
  created_at: string
  updated_at: string
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface EmployeeFilters {
  search?: string
  department?: number
  position?: number
  hire_date?: string
  ordering?: 'employee_id' | 'hire_date' | 'created_at' | 'updated_at' |
    '-employee_id' | '-hire_date' | '-created_at' | '-updated_at'
}

export interface EmployeeListParams extends EmployeeFilters {
  page?: number
  page_size?: number
}

export async function getEmployees(
  params: EmployeeListParams = {},
): Promise<PaginatedResponse<EmployeeProfile>> {
  const response = await api.get<PaginatedResponse<EmployeeProfile>>(
    '/employees/',
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
