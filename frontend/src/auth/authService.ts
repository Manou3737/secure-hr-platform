import api from '../api/client'

export interface AuthTokens {
  access: string
  refresh: string
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

export async function refreshAccessToken(
  refreshToken: string,
): Promise<AuthTokens> {
  const response = await api.post<AuthTokens>(
    '/auth/refresh/',
    { refresh: refreshToken },
  )

  return response.data
}

export async function logout(
  refreshToken: string,
): Promise<void> {
  await api.post('/auth/logout/', {
    refresh: refreshToken,
  })
}
