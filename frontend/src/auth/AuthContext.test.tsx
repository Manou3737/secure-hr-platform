import { act, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getCurrentUser,
  logout,
  refreshAccessToken,
} from './authService'

import { AuthProvider } from './AuthContext'
import { useAuth } from './useAuth'
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from './tokenStore'

import type { AuthTokens, AuthUser } from './authService'

vi.mock('./authService', () => ({
  login: vi.fn(),
  getCurrentUser: vi.fn(),
  logout: vi.fn(),
  refreshAccessToken: vi.fn(),
}))

vi.mock('../api/client', () => ({
  setSessionExpiredHandler: vi.fn(),
  default: {
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
}))

const tokens: AuthTokens = {
  access: 'test-access',
  refresh: 'test-refresh',
}

const user: AuthUser = {
  id: 1,
  email: 'employee@example.com',
  name: 'Test Employee',
  role: 'EMPLOYEE',
  email_verified: true,
  is_active: true,
}

function AuthProbe() {
  const auth = useAuth()

  return (
    <div>
      <p data-testid="loading">{String(auth.isLoading)}</p>
      <p data-testid="authenticated">
        {String(auth.isAuthenticated)}
      </p>
      <p data-testid="user">
        {auth.user?.email ?? 'No user'}
      </p>
      <button onClick={() => auth.logout()}>
        Logout
      </button>
    </div>
  )
}

function renderAuthProvider() {
  return render(
    <AuthProvider>
      <AuthProbe />
    </AuthProvider>,
  )
}

describe('AuthContext', () => {
  beforeEach(() => {
    clearTokens()
    sessionStorage.clear()
    vi.clearAllMocks()
  })

  it('starts unauthenticated when no refresh token exists', async () => {
    renderAuthProvider()

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false')
    })

    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
    expect(screen.getByTestId('user')).toHaveTextContent('No user')
    expect(refreshAccessToken).not.toHaveBeenCalled()
  })

  it('restores a valid session', async () => {
    sessionStorage.setItem('secure_hr_refresh_token', tokens.refresh)

    vi.mocked(refreshAccessToken).mockResolvedValue(tokens)
    vi.mocked(getCurrentUser).mockResolvedValue(user)

    renderAuthProvider()

    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('true')
    })

    expect(screen.getByTestId('user')).toHaveTextContent(user.email)
    expect(getAccessToken()).toBe(tokens.access)
    expect(getRefreshToken()).toBe(tokens.refresh)
  })

  it('clears an invalid session', async () => {
    sessionStorage.setItem('secure_hr_refresh_token', tokens.refresh)

    vi.mocked(refreshAccessToken).mockRejectedValue(
      new Error('Invalid refresh token'),
    )

    renderAuthProvider()

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false')
    })

    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
    expect(getRefreshToken()).toBeNull()
    expect(getAccessToken()).toBeNull()
  })

  it('logs out and clears the local session', async () => {
    setTokens(tokens)
    vi.mocked(refreshAccessToken).mockResolvedValue(tokens)
    vi.mocked(getCurrentUser).mockResolvedValue(user)
    vi.mocked(logout).mockResolvedValue(undefined)

    renderAuthProvider()

    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('true')
    })

    await act(async () => {
      screen.getByRole('button', { name: 'Logout' }).click()
    })

    expect(logout).toHaveBeenCalledWith(tokens.refresh)
    expect(getRefreshToken()).toBeNull()
    expect(getAccessToken()).toBeNull()
    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
  })
})
