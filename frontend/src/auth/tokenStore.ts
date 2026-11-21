import type { AuthTokens } from './authService'

const REFRESH_TOKEN_KEY = 'secure_hr_refresh_token'

let accessToken: string | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setTokens(tokens: AuthTokens): void {
  accessToken = tokens.access
  sessionStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh)
}

export function clearTokens(): void {
  accessToken = null
  sessionStorage.removeItem(REFRESH_TOKEN_KEY)
}
