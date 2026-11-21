import { beforeEach, describe, expect, it } from 'vitest'

import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setAccessToken,
  setTokens,
} from './tokenStore'

import type { AuthTokens } from './authService'

describe('tokenStore', () => {
  const tokens: AuthTokens = {
    access: 'test-access-token',
    refresh: 'test-refresh-token',
  }

  beforeEach(() => {
    clearTokens()
    sessionStorage.clear()
  })

  it('stores the access token in memory', () => {
    setAccessToken('new-access-token')

    expect(getAccessToken()).toBe('new-access-token')
  })

  it('stores the refresh token in sessionStorage', () => {
    setTokens(tokens)

    expect(getRefreshToken()).toBe('test-refresh-token')
    expect(sessionStorage.getItem('secure_hr_refresh_token'))
      .toBe('test-refresh-token')
  })

  it('stores both tokens correctly', () => {
    setTokens(tokens)

    expect(getAccessToken()).toBe(tokens.access)
    expect(getRefreshToken()).toBe(tokens.refresh)
  })

  it('clears both tokens', () => {
    setTokens(tokens)

    clearTokens()

    expect(getAccessToken()).toBeNull()
    expect(getRefreshToken()).toBeNull()
    expect(
      sessionStorage.getItem('secure_hr_refresh_token'),
    ).toBeNull()
  })

  it('can clear tokens when no session exists', () => {
    expect(() => clearTokens()).not.toThrow()

    expect(getAccessToken()).toBeNull()
    expect(getRefreshToken()).toBeNull()
  })
})
