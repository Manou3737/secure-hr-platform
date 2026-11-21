import api from './client'
import type { PaginatedResponse } from './employeeService'

export interface Department {
  id: number
  name: string
  code: string
  description: string
}

export async function getDepartments(): Promise<
  PaginatedResponse<Department>
> {
  const response = await api.get<PaginatedResponse<Department>>(
    '/employees/departments/',
  )

  return response.data
}
