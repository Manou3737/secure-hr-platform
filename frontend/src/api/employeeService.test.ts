import { beforeEach, describe, expect, it, vi } from 'vitest'

import api from './client'
import { getEmployees } from './employeeService'

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
  },
}))

describe('employeeService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches employees with default pagination', async () => {
    const responseData = {
      count: 1,
      next: null,
      previous: null,
      results: [],
    }

    vi.mocked(api.get).mockResolvedValue({
      data: responseData,
    } as never)

    const result = await getEmployees()

    expect(api.get).toHaveBeenCalledWith('/employees/', {
      params: {
        page: 1,
        page_size: 20,
      },
    })

    expect(result).toEqual(responseData)
  })

  it('sends custom pagination parameters', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        count: 0,
        next: null,
        previous: null,
        results: [],
      },
    } as never)

    await getEmployees({
      page: 2,
      page_size: 10,
    })

    expect(api.get).toHaveBeenCalledWith('/employees/', {
      params: {
        page: 2,
        page_size: 10,
      },
    })
  })

  it('sends supported filters and ordering', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        count: 0,
        next: null,
        previous: null,
        results: [],
      },
    } as never)

    await getEmployees({
      search: 'Engineering',
      department: 3,
      position: 5,
      hire_date: '2026-01-15',
      ordering: '-hire_date',
    })

    expect(api.get).toHaveBeenCalledWith('/employees/', {
      params: {
        search: 'Engineering',
        department: 3,
        position: 5,
        hire_date: '2026-01-15',
        ordering: '-hire_date',
        page: 1,
        page_size: 20,
      },
    })
  })
})
