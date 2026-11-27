import api, { ensureCsrfCookie } from '../api/client'

export interface AuthTokens {
  access: string
}

export interface AuthUser {
  id: number
  email: string
  name: string
  role: 'SUPER_ADMIN' | 'HR_ADMIN' | 'HR_MANAGER' | 'EMPLOYEE'
  email_verified: boolean
  is_active: boolean
}

export async function login(
  email: string,
  password: string,
): Promise<AuthTokens> {
  await ensureCsrfCookie()

  const response = await api.post<AuthTokens>(
    '/auth/login/',
    { email, password },
  )

  return response.data
}

export async function getCurrentUser(
  accessToken: string,
): Promise<AuthUser> {
  const response = await api.get<AuthUser>(
    '/auth/me/',
    {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    },
  )

  return response.data
}

export async function refreshAccessToken(): Promise<AuthTokens> {
  await ensureCsrfCookie()

  const response = await api.post<AuthTokens>(
    '/auth/refresh/',
  )

  return response.data
}

export async function logout(): Promise<void> {
  await ensureCsrfCookie()

  await api.post('/auth/logout/')
}
