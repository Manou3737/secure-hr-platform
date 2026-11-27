import { beforeEach, describe, expect, it } from 'vitest'

import {
  clearTokens,
  getAccessToken,
  setAccessToken,
} from './tokenStore'

describe('tokenStore', () => {
  beforeEach(() => {
    clearTokens()
  })

  it('stores the access token in memory', () => {
    setAccessToken('new-access-token')

    expect(getAccessToken()).toBe('new-access-token')
  })

  it('returns null when no access token exists', () => {
    expect(getAccessToken()).toBeNull()
  })

  it('replaces the previous access token', () => {
    setAccessToken('old-access-token')
    setAccessToken('new-access-token')

    expect(getAccessToken()).toBe('new-access-token')
  })

  it('clears the access token', () => {
    setAccessToken('test-access-token')

    clearTokens()

    expect(getAccessToken()).toBeNull()
  })

  it('can clear tokens when no session exists', () => {
    expect(() => clearTokens()).not.toThrow()

    expect(getAccessToken()).toBeNull()
  })
})
