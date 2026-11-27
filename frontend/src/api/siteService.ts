import api from './client'
import type { PaginatedResponse } from './employeeService'

export interface Site {
  id: number
  name: string
  code: string
  address: string
  department: number
  is_active: boolean
}

export async function getSites(): Promise<PaginatedResponse<Site>> {
  const response = await api.get<PaginatedResponse<Site>>(
    '/employees/sites/',
  )

  return response.data
}
