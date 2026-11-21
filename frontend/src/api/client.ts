import axios, {
  type InternalAxiosRequestConfig,
} from 'axios'

import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from '../auth/tokenStore'

import type { AuthTokens } from '../auth/authService'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || '/api/v1'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15_000,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  },
})

type RetryableRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean
}

let refreshPromise: Promise<AuthTokens> | null = null

let sessionExpiredHandler: (() => void) | null = null

export function setSessionExpiredHandler(
  handler: (() => void) | null,
): void {
  sessionExpiredHandler = handler
}

function expireSession(): void {
  clearTokens()
  sessionExpiredHandler?.()
}

api.interceptors.request.use((config) => {
  const accessToken = getAccessToken()

  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }

  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!axios.isAxiosError(error)) {
      return Promise.reject(error)
    }

    const originalRequest = error.config as
      | RetryableRequestConfig
      | undefined

    if (
      error.response?.status !== 401 ||
      !originalRequest ||
      originalRequest._retry
    ) {
      return Promise.reject(error)
    }

    const requestUrl = originalRequest.url ?? ''

    const excludedEndpoints = [
      '/auth/login/',
      '/auth/refresh/',
      '/auth/logout/',
    ]

    if (
      excludedEndpoints.some((endpoint) =>
        requestUrl.includes(endpoint),
      )
    ) {
      return Promise.reject(error)
    }

    originalRequest._retry = true

    const refreshToken = getRefreshToken()

    if (!refreshToken) {
      expireSession()
      return Promise.reject(error)
    }

    if (!refreshPromise) {
      refreshPromise = axios
        .post<AuthTokens>(
          '/auth/refresh/',
          { refresh: refreshToken },
          {
            baseURL: API_BASE_URL,
            timeout: 15_000,
            headers: {
              Accept: 'application/json',
              'Content-Type': 'application/json',
            },
          },
        )
        .then(({ data }) => {
          if (!data.access || !data.refresh) {
            throw new Error(
              'The refresh endpoint did not return both tokens.',
            )
          }

          setTokens(data)

          return data
        })
        .catch((refreshError: unknown) => {
          expireSession()
          throw refreshError
        })
        .finally(() => {
          refreshPromise = null
        })
    }

    try {
      const tokens = await refreshPromise

      originalRequest.headers.Authorization =
        `Bearer ${tokens.access}`

      return api(originalRequest)
    } catch (refreshError) {
      return Promise.reject(refreshError)
    }
  },
)

export default api
