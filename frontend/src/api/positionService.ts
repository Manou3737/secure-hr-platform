import api from './client'
import type { PaginatedResponse } from './employeeService'

export interface Position {
  id: number
  title: string
  department: number
  description: string
}

export async function getPositions(
  department?: number,
): Promise<PaginatedResponse<Position>> {
  const response = await api.get<PaginatedResponse<Position>>(
    '/employees/positions/',
    {
      params: department ? { department } : {},
    },
  )

  return response.data
}
