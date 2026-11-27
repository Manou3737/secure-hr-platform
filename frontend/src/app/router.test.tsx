import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AppRouter from './router'
import { ToastProvider } from '../components/ui/ToastProvider'

const { authState } = vi.hoisted(() => ({
  authState: {
    user: {
      id: 1,
      name: 'Test User',
      email: 'test@example.com',
      role: 'EMPLOYEE',
      email_verified: true,
      is_active: true,
    } as {
      id: number
      name: string
      email: string
      role: string
      email_verified: boolean
      is_active: boolean
    } | null,
    isAuthenticated: true,
    isLoading: false,
    logout: vi.fn(),
    login: vi.fn(),
  },
}))

vi.mock('../auth/useAuth', () => ({
  useAuth: () => authState,
}))

vi.mock('../pages/LoginPage', () => ({
  default: () => <h1>Login page test</h1>,
}))

vi.mock('../pages/DashboardPage', () => ({
  default: () => <h1>Dashboard page test</h1>,
}))

vi.mock('../pages/DocumentsPage', () => ({
  default: () => <h2>Documents page test</h2>,
}))

vi.mock('../pages/TasksPage', () => ({
  default: () => <h2>Tasks page test</h2>,
}))

vi.mock('../pages/DocumentDetailPage', () => ({
  default: () => <h2>Document detail page test</h2>,
}))

vi.mock('../pages/TaskDetailPage', () => ({
  default: () => <h2>Task detail page test</h2>,
}))

function renderRouter(initialRoute: string) {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[initialRoute]}>
        <AppRouter />
      </MemoryRouter>
    </ToastProvider>,
  )
}

describe('AppRouter - Documents and Tasks routes', () => {
  beforeEach(() => {
    authState.user = {
      id: 1,
      name: 'Test User',
      email: 'test@example.com',
      role: 'EMPLOYEE',
      email_verified: true,
      is_active: true,
    }
    authState.isAuthenticated = true
    authState.isLoading = false
  })

  it.each([
    'EMPLOYEE',
    'HR_MANAGER',
    'HR_ADMIN',
    'SUPER_ADMIN',
  ])('allows %s to access /documents', async (role) => {
    authState.user = {
      id: 1,
      name: 'Test User',
      email: 'test@example.com',
      role,
      email_verified: true,
      is_active: true,
    }

    renderRouter('/documents')

    expect(
      await screen.findByRole('heading', {
        name: 'Documents page test',
      }),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('heading', { name: 'HR Documents' }),
    ).toBeInTheDocument()
  })

  it.each([
    'EMPLOYEE',
    'HR_MANAGER',
    'HR_ADMIN',
    'SUPER_ADMIN',
  ])('allows %s to access /tasks', async (role) => {
    authState.user = {
      id: 1,
      name: 'Test User',
      email: 'test@example.com',
      role,
      email_verified: true,
      is_active: true,
    }

    renderRouter('/tasks')

    expect(
      await screen.findByRole('heading', {
        name: 'Tasks page test',
      }),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('heading', { name: 'Onboarding Tasks' }),
    ).toBeInTheDocument()
  })

  it.each([
    'EMPLOYEE',
    'HR_MANAGER',
    'HR_ADMIN',
    'SUPER_ADMIN',
  ])('allows %s to access /documents/:id', async (role) => {
    authState.user = {
      id: 1,
      name: 'Test User',
      email: 'test@example.com',
      role,
      email_verified: true,
      is_active: true,
    }

    renderRouter('/documents/550e8400-e29b-41d4-a716-446655440000')

    expect(
      await screen.findByRole('heading', {
        name: 'Document detail page test',
      }),
    ).toBeInTheDocument()
  })

  it.each([
    'EMPLOYEE',
    'HR_MANAGER',
    'HR_ADMIN',
    'SUPER_ADMIN',
  ])('allows %s to access /tasks/:id', async (role) => {
    authState.user = {
      id: 1,
      name: 'Test User',
      email: 'test@example.com',
      role,
      email_verified: true,
      is_active: true,
    }

    renderRouter('/tasks/550e8400-e29b-41d4-a716-446655440000')

    expect(
      await screen.findByRole('heading', {
        name: 'Task detail page test',
      }),
    ).toBeInTheDocument()
  })

  it.each([
    '/documents',
    '/documents/550e8400-e29b-41d4-a716-446655440000',
    '/tasks',
    '/tasks/550e8400-e29b-41d4-a716-446655440000',
  ])(
    'redirects unauthenticated users from %s to /login',
    async (route) => {
      authState.isAuthenticated = false
      authState.user = null

      renderRouter(route)

      expect(
        await screen.findByRole('heading', {
          name: 'Login page test',
        }),
      ).toBeInTheDocument()
    },
  )

  it('displays Documents and Tasks links in the main navigation', async () => {
    renderRouter('/dashboard')

    // Attendre le chargement de la page lazy
    await screen.findByRole('heading', {
      name: 'Dashboard page test',
    })

    const navigation = screen.getByRole('navigation', {
      name: 'Main navigation',
    })

    expect(
      navigation.querySelector('a[href="/documents"]'),
    ).toBeInTheDocument()

    expect(
      navigation.querySelector('a[href="/tasks"]'),
    ).toBeInTheDocument()
  })
})
