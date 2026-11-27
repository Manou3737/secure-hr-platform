import {
  AxiosError,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'

import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest'

import { waitFor } from '@testing-library/react'

import api, { setSessionExpiredHandler } from './client'

import {
  clearTokens,
  getAccessToken,
  setAccessToken,
} from '../auth/tokenStore'

const oldAccessToken = 'old-access-token'
const newAccessToken = 'new-access-token'

const originalAdapter = api.defaults.adapter

function createUnauthorizedError(
  config: InternalAxiosRequestConfig,
): AxiosError {
  const response: AxiosResponse = {
    data: { detail: 'Token expired' },
    status: 401,
    statusText: 'Unauthorized',
    headers: {},
    config,
  }

  return new AxiosError(
    'Request failed with status code 401',
    'ERR_BAD_REQUEST',
    config,
    undefined,
    response,
  )
}

function createSuccessResponse(
  config: InternalAxiosRequestConfig,
  data: unknown = { success: true },
): AxiosResponse {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config,
  }
}

describe('Axios JWT interceptors', () => {
  beforeEach(() => {
    clearTokens()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    setSessionExpiredHandler(null)
    clearTokens()
    api.defaults.adapter = originalAdapter
    vi.restoreAllMocks()
  })

  it('refreshes an expired access token using the cookie and retries the request', async () => {
    setAccessToken(oldAccessToken)

    let refreshCount = 0
    let refreshRequestData: unknown = 'not-checked'

    const adapter: AxiosAdapter = async (config) => {
      if (config.url?.includes('/auth/csrf/')) {
        return createSuccessResponse(config)
      }

      if (config.url?.includes('/auth/refresh/')) {
        refreshCount += 1
        refreshRequestData = config.data
        return createSuccessResponse(config, { access: newAccessToken })
      }

      const authorization = config.headers.get('Authorization')

      if (authorization === `Bearer ${oldAccessToken}`) {
        throw createUnauthorizedError(config)
      }

      return createSuccessResponse(config)
    }

    api.defaults.adapter = adapter

    const response = await api.get('/employees/')

    expect(response.status).toBe(200)
    expect(refreshCount).toBe(1)
    expect(refreshRequestData).toBeUndefined()
    expect(getAccessToken()).toBe(newAccessToken)
  })

  it('uses only one refresh request for simultaneous 401 responses', async () => {
    setAccessToken(oldAccessToken)

    let unauthorizedCount = 0
    let refreshCount = 0
    let releaseUnauthorized!: () => void
    let resolveRefresh!: () => void

    const unauthorizedBarrier = new Promise<void>((resolve) => {
      releaseUnauthorized = resolve
    })

    const refreshBarrier = new Promise<void>((resolve) => {
      resolveRefresh = resolve
    })

    const adapter: AxiosAdapter = async (config) => {
      if (config.url?.includes('/auth/csrf/')) {
        return createSuccessResponse(config)
      }

      if (config.url?.includes('/auth/refresh/')) {
        refreshCount += 1
        await refreshBarrier
        return createSuccessResponse(config, { access: newAccessToken })
      }

      const authorization = config.headers.get('Authorization')

      if (authorization === `Bearer ${oldAccessToken}`) {
        unauthorizedCount += 1

        if (unauthorizedCount === 2) {
          releaseUnauthorized()
        }

        await unauthorizedBarrier
        throw createUnauthorizedError(config)
      }

      return createSuccessResponse(config)
    }

    api.defaults.adapter = adapter

    const requests = Promise.all([
      api.get('/employees/'),
      api.get('/departments/'),
    ])

    await waitFor(() => {
      expect(refreshCount).toBe(1)
    })

    resolveRefresh()

    const responses = await requests

    expect(responses).toHaveLength(2)
    expect(responses[0].status).toBe(200)
    expect(responses[1].status).toBe(200)
    expect(refreshCount).toBe(1)
    expect(getAccessToken()).toBe(newAccessToken)
  })

  it('expires the session when no access token is available', async () => {
    const adapter: AxiosAdapter = async (config) => {
      throw createUnauthorizedError(config)
    }

    api.defaults.adapter = adapter

    const expiredHandler = vi.fn()
    setSessionExpiredHandler(expiredHandler)

    await expect(api.get('/employees/')).rejects.toMatchObject({
      response: {
        status: 401,
      },
    })

    expect(expiredHandler).toHaveBeenCalledTimes(1)
    expect(getAccessToken()).toBeNull()
  })

  it('clears the session when cookie-based refresh fails', async () => {
    setAccessToken(oldAccessToken)

    const adapter: AxiosAdapter = async (config) => {
      if (config.url?.includes('/auth/csrf/')) {
        return createSuccessResponse(config)
      }

      if (config.url?.includes('/auth/refresh/')) {
        throw createUnauthorizedError(config)
      }

      throw createUnauthorizedError(config)
    }

    api.defaults.adapter = adapter

    const expiredHandler = vi.fn()
    setSessionExpiredHandler(expiredHandler)

    await expect(api.get('/employees/')).rejects.toMatchObject({
      response: {
        status: 401,
      },
    })

    expect(expiredHandler).toHaveBeenCalledTimes(1)
    expect(getAccessToken()).toBeNull()
  })
})
