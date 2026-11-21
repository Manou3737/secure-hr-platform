import axios, {
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
  getRefreshToken,
  setTokens,
} from '../auth/tokenStore'

import type { AuthTokens } from '../auth/authService'

const oldTokens: AuthTokens = {
  access: 'old-access-token',
  refresh: 'old-refresh-token',
}

const newTokens: AuthTokens = {
  access: 'new-access-token',
  refresh: 'new-refresh-token',
}

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
): AxiosResponse {
  return {
    data: { success: true },
    status: 200,
    statusText: 'OK',
    headers: {},
    config,
  }
}

describe('Axios JWT interceptors', () => {
  beforeEach(() => {
    clearTokens()
    sessionStorage.clear()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    setSessionExpiredHandler(null)
    clearTokens()
    api.defaults.adapter = originalAdapter
    vi.restoreAllMocks()
  })

  it('refreshes an expired access token and retries the request', async () => {
    setTokens(oldTokens)

    const adapter: AxiosAdapter = async (config) => {
      const authorization = config.headers.get('Authorization')

      if (authorization === `Bearer ${oldTokens.access}`) {
        throw createUnauthorizedError(config)
      }

      return createSuccessResponse(config)
    }

    api.defaults.adapter = adapter

    const refreshSpy = vi
      .spyOn(axios, 'post')
      .mockResolvedValue({
        data: newTokens,
      } as AxiosResponse<AuthTokens>)

    const response = await api.get('/employees/')

    expect(response.status).toBe(200)
    expect(refreshSpy).toHaveBeenCalledTimes(1)
    expect(refreshSpy).toHaveBeenCalledWith(
      '/auth/refresh/',
      { refresh: oldTokens.refresh },
      expect.objectContaining({
        baseURL: expect.any(String),
      }),
    )

    expect(getAccessToken()).toBe(newTokens.access)
    expect(getRefreshToken()).toBe(newTokens.refresh)
  })

  it('uses only one refresh request for simultaneous 401 responses', async () => {
    setTokens(oldTokens)

    let unauthorizedCount = 0
    let releaseUnauthorized!: () => void

    const unauthorizedBarrier = new Promise<void>((resolve) => {
      releaseUnauthorized = resolve
    })

    const adapter: AxiosAdapter = async (config) => {
      const authorization = config.headers.get('Authorization')

      if (authorization === `Bearer ${oldTokens.access}`) {
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

    let resolveRefresh!: (
      response: AxiosResponse<AuthTokens>,
    ) => void

    const pendingRefresh = new Promise<AxiosResponse<AuthTokens>>(
      (resolve) => {
        resolveRefresh = resolve
      },
    )

    const refreshSpy = vi
      .spyOn(axios, 'post')
      .mockReturnValue(pendingRefresh as never)

    const requests = Promise.all([
      api.get('/employees/'),
      api.get('/departments/'),
    ])

    await waitFor(() => {
      expect(refreshSpy).toHaveBeenCalledTimes(1)
    })

    resolveRefresh({
      data: newTokens,
    } as AxiosResponse<AuthTokens>)

    const responses = await requests

    expect(responses).toHaveLength(2)
    expect(responses[0].status).toBe(200)
    expect(responses[1].status).toBe(200)
    expect(refreshSpy).toHaveBeenCalledTimes(1)
    expect(getAccessToken()).toBe(newTokens.access)
    expect(getRefreshToken()).toBe(newTokens.refresh)
  })

  it('expires the session when no refresh token exists', async () => {
    const adapter: AxiosAdapter = async (config) => {
      throw createUnauthorizedError(config)
    }

    api.defaults.adapter = adapter

    const expiredHandler = vi.fn()
    setSessionExpiredHandler(expiredHandler)

    const refreshSpy = vi.spyOn(axios, 'post')

    await expect(api.get('/employees/')).rejects.toMatchObject({
      response: {
        status: 401,
      },
    })

    expect(refreshSpy).not.toHaveBeenCalled()
    expect(expiredHandler).toHaveBeenCalledTimes(1)
    expect(getAccessToken()).toBeNull()
    expect(getRefreshToken()).toBeNull()
  })

  it('clears the session when refresh fails', async () => {
    setTokens(oldTokens)

    const adapter: AxiosAdapter = async (config) => {
      throw createUnauthorizedError(config)
    }

    api.defaults.adapter = adapter

    const expiredHandler = vi.fn()
    setSessionExpiredHandler(expiredHandler)

    vi.spyOn(axios, 'post').mockRejectedValue(
      new Error('Invalid refresh token'),
    )

    await expect(api.get('/employees/')).rejects.toThrow(
      'Invalid refresh token',
    )

    expect(expiredHandler).toHaveBeenCalledTimes(1)
    expect(getAccessToken()).toBeNull()
    expect(getRefreshToken()).toBeNull()
  })
})
