import { beforeEach, describe, expect, it, vi } from 'vitest'

import api from './client'
import { getDepartments } from './departmentService'

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
  },
}))

describe('departmentService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches departments from the API', async () => {
    const responseData = {
      count: 2,
      next: null,
      previous: null,
      results: [
        { id: 2, name: 'Engineering', code: 'ENG', description: '' },
        { id: 4, name: 'Finance', code: 'FIN', description: '' },
      ],
    }

    vi.mocked(api.get).mockResolvedValue({
      data: responseData,
    } as never)

    const result = await getDepartments()

    expect(api.get).toHaveBeenCalledWith('/employees/departments/')
    expect(result).toEqual(responseData)
  })
})
