import {
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from 'react'

import {
  login as loginRequest,
  getCurrentUser,
  logout as logoutRequest,
  refreshAccessToken,
  type AuthTokens,
  type AuthUser,
} from './authService'

import {
  clearTokens,
  getRefreshToken,
  setTokens as storeTokens,
} from './tokenStore'

import { setSessionExpiredHandler } from '../api/client'
import { AuthContext } from './context'

interface RestoredSession {
  tokens: AuthTokens
  user: AuthUser
}

let sessionRestorePromise: Promise<RestoredSession | null> | null = null

function restoreSession(): Promise<RestoredSession | null> {
  if (sessionRestorePromise) {
    return sessionRestorePromise
  }

  const refreshToken = getRefreshToken()

  if (!refreshToken) {
    return Promise.resolve(null)
  }

  sessionRestorePromise = (async () => {
    try {
      const tokens = await refreshAccessToken(refreshToken)

      if (!tokens.access || !tokens.refresh) {
        throw new Error('Invalid token response.')
      }

      storeTokens(tokens)

      const user = await getCurrentUser(tokens.access)

      return { tokens, user }
    } catch {
      clearTokens()
      return null
    }
  })().finally(() => {
    sessionRestorePromise = null
  })

  return sessionRestorePromise
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [tokens, setAuthTokens] = useState<AuthTokens | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const handleSessionExpired = useCallback(() => {
    clearTokens()
    setAuthTokens(null)
    setUser(null)
  }, [])

  useEffect(() => {
    setSessionExpiredHandler(handleSessionExpired)

    return () => {
      setSessionExpiredHandler(null)
    }
  }, [handleSessionExpired])

  useEffect(() => {
    let cancelled = false

    async function initializeSession() {
      const session = await restoreSession()

      if (cancelled) {
        return
      }

      if (session) {
        setAuthTokens(session.tokens)
        setUser(session.user)
      } else {
        setAuthTokens(null)
        setUser(null)
      }

      setIsLoading(false)
    }

    void initializeSession()

    return () => {
      cancelled = true
    }
  }, [])

  async function login(email: string, password: string): Promise<void> {
    setIsLoading(true)

    try {
      const authTokens = await loginRequest(email, password)
      const currentUser = await getCurrentUser(authTokens.access)

      storeTokens(authTokens)
      setAuthTokens(authTokens)
      setUser(currentUser)
    } catch (error) {
      clearTokens()
      setAuthTokens(null)
      setUser(null)
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  async function logout(): Promise<void> {
    const refreshToken = getRefreshToken()

    try {
      if (refreshToken) {
        await logoutRequest(refreshToken)
      }
    } finally {
      clearTokens()
      setAuthTokens(null)
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null && tokens !== null,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
