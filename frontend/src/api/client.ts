import axios, {
  type InternalAxiosRequestConfig,
} from 'axios'

import {
  clearTokens,
  getAccessToken,
  setAccessToken,
} from '../auth/tokenStore'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || '/api/v1'

interface AccessTokenResponse {
  access: string
}

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15_000,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  },
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
})

type RetryableRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean
}

let refreshPromise: Promise<string> | null = null

let sessionExpiredHandler: (() => void) | null = null

export function setSessionExpiredHandler(
  handler: (() => void) | null,
): void {
  sessionExpiredHandler = handler
}

export async function ensureCsrfCookie(): Promise<void> {
  await api.get('/auth/csrf/')
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

    if (!getAccessToken()) {
      expireSession()
      return Promise.reject(error)
    }

    if (!refreshPromise) {
      refreshPromise = (async () => {
        try {
          await ensureCsrfCookie()

          const { data } = await api.post<AccessTokenResponse>(
            '/auth/refresh/',
          )

          if (!data.access) {
            throw new Error(
              'The refresh endpoint did not return an access token.',
            )
          }

          setAccessToken(data.access)

          return data.access
        } catch (refreshError) {
          expireSession()
          throw refreshError
        } finally {
          refreshPromise = null
        }
      })()
    }

    try {
      const accessToken = await refreshPromise

      originalRequest.headers.Authorization =
        `Bearer ${accessToken}`

      return api(originalRequest)
    } catch (refreshError) {
      return Promise.reject(refreshError)
    }
  },
)

export default api
