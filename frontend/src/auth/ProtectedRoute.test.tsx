import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import {
  MemoryRouter,
  Route,
  Routes,
} from 'react-router-dom'

import ProtectedRoute from './ProtectedRoute'

const { authState } = vi.hoisted(() => ({
  authState: {
    value: {
      user: null as null | {
        id: number
        email: string
        name: string
        role: 'SUPER_ADMIN' | 'HR_ADMIN' | 'HR_MANAGER' | 'EMPLOYEE'
        email_verified: boolean
        is_active: boolean
      },
      isAuthenticated: false,
      isLoading: false,
    },
  },
}))

vi.mock('./useAuth', () => ({
  useAuth: () => ({
    ...authState.value,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}))

const hrManager = {
  id: 1,
  email: 'manager@example.com',
  name: 'HR Manager',
  role: 'HR_MANAGER' as const,
  email_verified: true,
  is_active: true,
}

function renderProtectedRoute(
  initialPath = '/protected',
  roles?: ('SUPER_ADMIN' | 'HR_ADMIN' | 'HR_MANAGER' | 'EMPLOYEE')[],
) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/login" element={<div>Login page</div>} />
        <Route path="/dashboard" element={<div>Dashboard page</div>} />

        <Route element={<ProtectedRoute roles={roles} />}>
          <Route
            path="/protected"
            element={<div>Protected page content</div>}
          />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    authState.value = {
      user: null,
      isAuthenticated: false,
      isLoading: false,
    }
  })

  it('displays a loading state while authentication is being checked', () => {
    authState.value.isLoading = true

    renderProtectedRoute()

    expect(screen.getByRole('status')).toHaveTextContent(
      'Checking authentication...',
    )
    expect(screen.queryByText('Protected page content')).not.toBeInTheDocument()
  })

  it('redirects unauthenticated users to login', () => {
    renderProtectedRoute()

    expect(screen.getByText('Login page')).toBeInTheDocument()
    expect(screen.queryByText('Protected page content')).not.toBeInTheDocument()
  })

  it('allows authenticated users to access protected routes', () => {
    authState.value = {
      user: hrManager,
      isAuthenticated: true,
      isLoading: false,
    }

    renderProtectedRoute()

    expect(screen.getByText('Protected page content')).toBeInTheDocument()
  })

  it('allows users whose role is included in the allowed roles', () => {
    authState.value = {
      user: hrManager,
      isAuthenticated: true,
      isLoading: false,
    }

    renderProtectedRoute('/protected', ['HR_MANAGER', 'HR_ADMIN'])

    expect(screen.getByText('Protected page content')).toBeInTheDocument()
  })

  it('redirects authenticated users with unauthorized roles to dashboard', () => {
    authState.value = {
      user: {
        ...hrManager,
        role: 'EMPLOYEE',
      },
      isAuthenticated: true,
      isLoading: false,
    }

    renderProtectedRoute('/protected', ['HR_MANAGER', 'HR_ADMIN'])

    expect(screen.getByText('Dashboard page')).toBeInTheDocument()
    expect(screen.queryByText('Protected page content')).not.toBeInTheDocument()
  })
})
