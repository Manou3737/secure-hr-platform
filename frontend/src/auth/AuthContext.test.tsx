import { act, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  login,
  getCurrentUser,
  logout,
  refreshAccessToken,
} from './authService'

import { AuthProvider } from './AuthContext'
import { useAuth } from './useAuth'
import { clearTokens, getAccessToken } from './tokenStore'

import type { AuthTokens, AuthUser } from './authService'

vi.mock('./authService', () => ({
  login: vi.fn(),
  getCurrentUser: vi.fn(),
  logout: vi.fn(),
  refreshAccessToken: vi.fn(),
}))

vi.mock('../api/client', () => ({
  setSessionExpiredHandler: vi.fn(),
}))

const tokens: AuthTokens = {
  access: 'test-access',
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
      <button onClick={() => auth.login('employee@example.com', 'password')}>
        Login
      </button>
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
    vi.clearAllMocks()
  })

  it('attempts cookie-based session restoration on startup', async () => {
    vi.mocked(refreshAccessToken).mockRejectedValue(
      new Error('No valid refresh cookie'),
    )

    renderAuthProvider()

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false')
    })

    expect(refreshAccessToken).toHaveBeenCalledTimes(1)
    expect(refreshAccessToken).toHaveBeenCalledWith()
    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
    expect(screen.getByTestId('user')).toHaveTextContent('No user')
    expect(getAccessToken()).toBeNull()
  })

  it('restores a valid session using the refresh cookie', async () => {
    vi.mocked(refreshAccessToken).mockResolvedValue(tokens)
    vi.mocked(getCurrentUser).mockResolvedValue(user)

    renderAuthProvider()

    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('true')
    })

    expect(refreshAccessToken).toHaveBeenCalledTimes(1)
    expect(getCurrentUser).toHaveBeenCalledWith(tokens.access)
    expect(screen.getByTestId('user')).toHaveTextContent(user.email)
    expect(getAccessToken()).toBe(tokens.access)
  })

  it('clears the local session when cookie-based restoration fails', async () => {
    vi.mocked(refreshAccessToken).mockRejectedValue(
      new Error('Invalid refresh cookie'),
    )

    renderAuthProvider()

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false')
    })

    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
    expect(getAccessToken()).toBeNull()
  })

  it('logs in and stores only the access token in memory', async () => {
    vi.mocked(refreshAccessToken).mockRejectedValue(
      new Error('No valid refresh cookie'),
    )
    vi.mocked(login).mockResolvedValue(tokens)
    vi.mocked(getCurrentUser).mockResolvedValue(user)

    renderAuthProvider()

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false')
    })

    await act(async () => {
      screen.getByRole('button', { name: 'Login' }).click()
    })

    expect(login).toHaveBeenCalledWith('employee@example.com', 'password')
    expect(getCurrentUser).toHaveBeenCalledWith(tokens.access)
    expect(getAccessToken()).toBe(tokens.access)
    expect(screen.getByTestId('authenticated')).toHaveTextContent('true')
    expect(screen.getByTestId('user')).toHaveTextContent(user.email)
  })

  it('logs out and clears the local session', async () => {
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

    expect(logout).toHaveBeenCalledWith()
    expect(getAccessToken()).toBeNull()
    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
    expect(screen.getByTestId('user')).toHaveTextContent('No user')
  })
})
