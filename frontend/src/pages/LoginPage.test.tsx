import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  MemoryRouter,
  Route,
  Routes,
} from 'react-router-dom'

import LoginPage from './LoginPage'

const { loginMock, loadingState } = vi.hoisted(() => ({
  loginMock: vi.fn(),
  loadingState: { value: false },
}))

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({
    login: loginMock,
    isLoading: loadingState.value,
  }),
}))

function renderLoginPage() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/dashboard"
          element={<div>Dashboard page content</div>}
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    loginMock.mockReset()
    loadingState.value = false
  })

  it('renders required email and password fields', () => {
    renderLoginPage()

    expect(screen.getByLabelText('Email')).toBeRequired()
    expect(screen.getByLabelText('Password')).toBeRequired()
    expect(
      screen.getByRole('button', { name: 'Sign in' }),
    ).toBeInTheDocument()
  })

  it('logs in successfully and redirects to the dashboard', async () => {
    const user = userEvent.setup()
    loginMock.mockResolvedValue(undefined)

    renderLoginPage()

    await user.type(
      screen.getByLabelText('Email'),
      'admin@example.com',
    )

    await user.type(
      screen.getByLabelText('Password'),
      'SecurePassword123!',
    )

    await user.click(
      screen.getByRole('button', { name: 'Sign in' }),
    )

    expect(loginMock).toHaveBeenCalledWith(
      'admin@example.com',
      'SecurePassword123!',
    )

    expect(
      await screen.findByText('Dashboard page content'),
    ).toBeInTheDocument()
  })

  it('submits the form when the user presses Enter', async () => {
    const user = userEvent.setup()
    loginMock.mockResolvedValue(undefined)

    renderLoginPage()

    await user.type(
      screen.getByLabelText('Email'),
      'admin@example.com',
    )

    await user.type(
      screen.getByLabelText('Password'),
      'SecurePassword123!',
    )

    await user.keyboard('{Enter}')

    expect(loginMock).toHaveBeenCalledTimes(1)
    expect(loginMock).toHaveBeenCalledWith(
      'admin@example.com',
      'SecurePassword123!',
    )

    expect(
      await screen.findByText('Dashboard page content'),
    ).toBeInTheDocument()
  })

  it('prevents duplicate submissions while login is pending', async () => {
    const user = userEvent.setup()

    let resolveLogin!: () => void

    loginMock.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          resolveLogin = resolve
        }),
    )

    renderLoginPage()

    await user.type(
      screen.getByLabelText('Email'),
      'admin@example.com',
    )

    await user.type(
      screen.getByLabelText('Password'),
      'SecurePassword123!',
    )

    const submitButton = screen.getByRole('button', {
      name: 'Sign in',
    })

    await user.click(submitButton)
    await user.click(submitButton)

    expect(loginMock).toHaveBeenCalledTimes(1)

    resolveLogin()

    expect(
      await screen.findByText('Dashboard page content'),
    ).toBeInTheDocument()
  })

  it('displays an error when login fails', async () => {
    const user = userEvent.setup()
    const technicalError =
      'Internal database error: SQL connection failed'

    loginMock.mockRejectedValueOnce(new Error(technicalError))

    renderLoginPage()

    await user.type(
      screen.getByLabelText('Email'),
      'admin@example.com',
    )

    await user.type(
      screen.getByLabelText('Password'),
      'WrongPassword123!',
    )

    await user.click(
      screen.getByRole('button', { name: 'Sign in' }),
    )

    expect(
      await screen.findByText(
        'Unable to sign in. Check your credentials and account verification.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText(technicalError)).not.toBeInTheDocument()
  })

  it('trims whitespace from the email before login', async () => {
    const user = userEvent.setup()
    loginMock.mockResolvedValue(undefined)

    renderLoginPage()

    await user.type(
      screen.getByLabelText('Email'),
      '  admin@example.com  ',
    )

    await user.type(
      screen.getByLabelText('Password'),
      'SecurePassword123!',
    )

    await user.click(
      screen.getByRole('button', { name: 'Sign in' }),
    )

    expect(loginMock).toHaveBeenCalledWith(
      'admin@example.com',
      'SecurePassword123!',
    )
  })

  it('announces login errors through an accessible alert', async () => {
    const user = userEvent.setup()
    const technicalError =
      'Internal database error: SQL connection failed'

    loginMock.mockRejectedValueOnce(new Error(technicalError))

    renderLoginPage()

    await user.type(
      screen.getByLabelText('Email'),
      'admin@example.com',
    )

    await user.type(
      screen.getByLabelText('Password'),
      'WrongPassword123!',
    )

    await user.click(
      screen.getByRole('button', { name: 'Sign in' }),
    )

    expect(
      await screen.findByRole('alert'),
    ).toHaveTextContent(
      'Unable to sign in. Check your credentials and account verification.',
    )
  })

  it('disables the submit button while authentication is loading', () => {
    loadingState.value = true

    renderLoginPage()

    expect(
      screen.getByRole('button', { name: 'Signing in...' }),
    ).toBeDisabled()
  })
})
