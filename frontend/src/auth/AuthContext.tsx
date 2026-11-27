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
  type AuthUser,
} from './authService'

import {
  clearTokens,
  setAccessToken,
} from './tokenStore'

import { setSessionExpiredHandler } from '../api/client'
import { AuthContext } from './context'

interface RestoredSession {
  accessToken: string
  user: AuthUser
}

let sessionRestorePromise: Promise<RestoredSession | null> | null = null

function restoreSession(): Promise<RestoredSession | null> {
  if (sessionRestorePromise) {
    return sessionRestorePromise
  }

  sessionRestorePromise = (async () => {
    try {
      const tokens = await refreshAccessToken()

      if (!tokens.access) {
        throw new Error('Invalid access token response.')
      }

      setAccessToken(tokens.access)

      const user = await getCurrentUser(tokens.access)

      return {
        accessToken: tokens.access,
        user,
      }
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
  const [accessToken, setAuthAccessToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const handleSessionExpired = useCallback(() => {
    clearTokens()
    setAuthAccessToken(null)
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
        setAuthAccessToken(session.accessToken)
        setUser(session.user)
      } else {
        setAuthAccessToken(null)
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

      if (!authTokens.access) {
        throw new Error('Invalid access token response.')
      }

      setAccessToken(authTokens.access)

      const currentUser = await getCurrentUser(authTokens.access)

      setAuthAccessToken(authTokens.access)
      setUser(currentUser)
    } catch (error) {
      clearTokens()
      setAuthAccessToken(null)
      setUser(null)
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  async function logout(): Promise<void> {
    try {
      await logoutRequest()
    } finally {
      clearTokens()
      setAuthAccessToken(null)
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null && accessToken !== null,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
