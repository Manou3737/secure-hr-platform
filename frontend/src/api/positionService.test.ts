import { beforeEach, describe, expect, it, vi } from 'vitest'

import api from './client'
import { getPositions } from './positionService'

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
  },
}))

describe('positionService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches positions without a department filter', async () => {
    const responseData = {
      count: 2,
      next: null,
      previous: null,
      results: [
        { id: 3, title: 'Developer', department: 2, description: '' },
        { id: 5, title: 'Financial Analyst', department: 4, description: '' },
      ],
    }

    vi.mocked(api.get).mockResolvedValue({
      data: responseData,
    } as never)

    const result = await getPositions()

    expect(api.get).toHaveBeenCalledWith('/employees/positions/', {
      params: {},
    })

    expect(result).toEqual(responseData)
  })

  it('filters positions by department', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        count: 1,
        next: null,
        previous: null,
        results: [
          { id: 3, title: 'Developer', department: 2, description: '' },
        ],
      },
    } as never)

    await getPositions(2)

    expect(api.get).toHaveBeenCalledWith('/employees/positions/', {
      params: {
        department: 2,
      },
    })
  })

  it('returns the API response data', async () => {
    const responseData = {
      count: 0,
      next: null,
      previous: null,
      results: [],
    }

    vi.mocked(api.get).mockResolvedValue({
      data: responseData,
    } as never)

    const result = await getPositions(2)

    expect(result).toEqual(responseData)
  })
})
