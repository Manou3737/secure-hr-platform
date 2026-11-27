
import { beforeEach, describe, expect, it, vi } from 'vitest'

import api from './client'
import { getDashboard } from './dashboardService'

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
  },
}))

describe('dashboardService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches dashboard metrics without filters', async () => {
    const responseData = {
      workforce: {},
      compliance: {},
      onboarding: {},
      operations: {},
      security: {},
      audit: {},
      risk: {},
      recruitment: {},
    }

    vi.mocked(api.get).mockResolvedValue({
      data: responseData,
    } as never)

    const result = await getDashboard()

    expect(api.get).toHaveBeenCalledWith(
      '/employees/dashboard/',
      { params: {} },
    )
    expect(result).toEqual(responseData)
  })

  it('sends department and period filters to the API', async () => {
    const responseData = {
      workforce: {},
      compliance: {},
      onboarding: {},
      operations: {},
      security: {},
      audit: {},
      risk: {},
      recruitment: {},
    }

    vi.mocked(api.get).mockResolvedValue({
      data: responseData,
    } as never)

    const result = await getDashboard({
      department_id: 4,
      days: 30,
    })

    expect(api.get).toHaveBeenCalledWith(
      '/employees/dashboard/',
      {
        params: {
          department_id: 4,
          days: 30,
        },
      },
    )
    expect(result).toEqual(responseData)
  })

  it('supports optional reference date and recent event limit', async () => {
    const responseData = {
      workforce: {},
      compliance: {},
      onboarding: {},
      operations: {},
      security: {},
      audit: {},
      risk: {},
      recruitment: {},
    }

    vi.mocked(api.get).mockResolvedValue({
      data: responseData,
    } as never)

    await getDashboard({
      days: 90,
      as_of: '2026-11-22',
      recent_limit: 20,
    })

    expect(api.get).toHaveBeenCalledWith(
      '/employees/dashboard/',
      {
        params: {
          days: 90,
          as_of: '2026-11-22',
          recent_limit: 20,
        },
      },
    )
  })
})
