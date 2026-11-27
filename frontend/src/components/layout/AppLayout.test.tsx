
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  MemoryRouter,
  Route,
  Routes,
} from 'react-router-dom'
import { ToastProvider } from '../ui/ToastProvider'
import AppLayout from './AppLayout'

const { logoutMock, currentUser } = vi.hoisted(() => ({
  logoutMock: vi.fn(),
  currentUser: {
    id: 1,
    name: 'Test HR Admin',
    email: 'admin@example.com',
    role: 'HR_ADMIN',
    email_verified: true,
    is_active: true,
  },
}))

vi.mock('../../auth/useAuth', () => ({
  useAuth: () => ({
    user: currentUser,
    logout: logoutMock,
  }),
}))

function renderLayout(initialRoute = '/dashboard') {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[initialRoute]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route
              path="/dashboard"
              element={<div>Dashboard content</div>}
            />
            <Route
              path="/profile"
              element={<div>Profile page content</div>}
            />
            <Route
              path="/employees"
              element={<div>Employees page content</div>}
            />
            <Route
              path="/compliance"
              element={<div>Compliance page content</div>}
            />
          </Route>
        </Routes>
      </MemoryRouter>
    </ToastProvider>,
  )
}

describe('AppLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    Object.assign(currentUser, {
      id: 1,
      name: 'Test HR Admin',
      email: 'admin@example.com',
      role: 'HR_ADMIN',
      email_verified: true,
      is_active: true,
    })

    logoutMock.mockResolvedValue(undefined)
  })

  it('displays the user information in the topbar', () => {
    renderLayout()

    expect(
      screen.getByRole('navigation', { name: 'Breadcrumb' }),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('navigation', { name: 'Main navigation' }),
    ).toBeInTheDocument()
  })

  it('shows Compliance navigation for HR_ADMIN', () => {
    currentUser.role = 'HR_ADMIN'

    renderLayout()

    expect(
      screen.getByRole('link', { name: /compliance/i }),
    ).toBeInTheDocument()
  })

  it('shows Compliance navigation for SUPER_ADMIN', () => {
    currentUser.role = 'SUPER_ADMIN'

    renderLayout()

    expect(
      screen.getByRole('link', { name: /compliance/i }),
    ).toBeInTheDocument()
  })

  it('shows Compliance navigation for HR_MANAGER', () => {
    currentUser.role = 'HR_MANAGER'

    renderLayout()

    expect(
      screen.getByRole('link', { name: /compliance/i }),
    ).toBeInTheDocument()
  })

  it('does not show Compliance navigation for EMPLOYEE', () => {
    currentUser.role = 'EMPLOYEE'

    renderLayout()

    expect(
      screen.queryByRole('link', { name: /compliance/i }),
    ).not.toBeInTheDocument()
  })

  it('opens the user menu and displays account information', async () => {
    const user = userEvent.setup()

    renderLayout()

    await user.click(
      screen.getByRole('button', { name: 'Open user menu' }),
    )

    expect(screen.getByRole('menu')).toBeInTheDocument()
    expect(screen.getByText('admin@example.com')).toBeInTheDocument()

    expect(
      screen.getByRole('menuitem', { name: 'My Profile' }),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('menuitem', { name: 'Sign out' }),
    ).toBeInTheDocument()
  })

  it('closes the user menu when Escape is pressed', async () => {
    const user = userEvent.setup()

    renderLayout()

    await user.click(
      screen.getByRole('button', { name: 'Open user menu' }),
    )

    expect(screen.getByRole('menu')).toBeInTheDocument()

    await user.keyboard('{Escape}')

    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('closes the user menu when clicking outside', async () => {
    const user = userEvent.setup()

    renderLayout()

    await user.click(
      screen.getByRole('button', { name: 'Open user menu' }),
    )

    expect(screen.getByRole('menu')).toBeInTheDocument()

    await user.click(screen.getByText('Dashboard content'))

    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('navigates to the profile page from the user menu', async () => {
    const user = userEvent.setup()

    renderLayout()

    await user.click(
      screen.getByRole('button', { name: 'Open user menu' }),
    )

    await user.click(
      screen.getByRole('menuitem', { name: 'My Profile' }),
    )

    expect(screen.getByText('Profile page content')).toBeInTheDocument()
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('opens and closes the mobile sidebar', async () => {
    const user = userEvent.setup()

    renderLayout()

    await user.click(
      screen.getByRole('button', { name: 'Open navigation' }),
    )

    expect(
      screen.getByRole('button', { name: 'Close navigation' }),
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: 'Close navigation' }),
    )

    expect(
      screen.queryByRole('button', { name: 'Close navigation' }),
    ).not.toBeInTheDocument()
  })

  it('closes the sidebar after selecting a navigation link', async () => {
    const user = userEvent.setup()

    renderLayout()

    await user.click(
      screen.getByRole('button', { name: 'Open navigation' }),
    )

    await user.click(
      screen.getByRole('link', { name: /Employees/ }),
    )

    expect(screen.getByText('Employees page content')).toBeInTheDocument()

    expect(
      screen.queryByRole('button', { name: 'Close navigation' }),
    ).not.toBeInTheDocument()
  })

  it('closes the sidebar when Escape is pressed', async () => {
    const user = userEvent.setup()

    renderLayout()

    await user.click(
      screen.getByRole('button', { name: 'Open navigation' }),
    )

    expect(
      screen.getByRole('button', { name: 'Close navigation' }),
    ).toBeInTheDocument()

    await user.keyboard('{Escape}')

    expect(
      screen.queryByRole('button', { name: 'Close navigation' }),
    ).not.toBeInTheDocument()
  })

  it('does not log out before confirmation from the user menu', async () => {
    const user = userEvent.setup()

    renderLayout()

    await user.click(
      screen.getByRole('button', { name: 'Open user menu' }),
    )

    await user.click(
      screen.getByRole('menuitem', { name: 'Sign out' }),
    )

    expect(screen.getByRole('alertdialog')).toBeInTheDocument()
    expect(logoutMock).not.toHaveBeenCalled()
  })

  it('logs out after confirmation from the user menu', async () => {
    const user = userEvent.setup()

    renderLayout()

    // Ouvrir le menu utilisateur
    await user.click(
      screen.getByRole('button', { name: 'Open user menu' }),
    )

    // Demander la déconnexion
    await user.click(
      screen.getByRole('menuitem', { name: 'Sign out' }),
    )

    // Vérifier que la confirmation est affichée
    const dialog = screen.getByRole('alertdialog')

    expect(dialog).toBeInTheDocument()
    expect(
      screen.getByText('Are you sure you want to sign out of your account?'),
    ).toBeInTheDocument()

    // Confirmer dans la boîte de dialogue uniquement
    await user.click(
      within(dialog).getByRole('button', { name: 'Sign out' }),
    )

    // Vérifier que la déconnexion est exécutée
    await waitFor(() => {
      expect(logoutMock).toHaveBeenCalledTimes(1)
    })

    // Vérifier l'affichage de la notification
    expect(
      await screen.findByRole('status'),
    ).toHaveTextContent('You have been signed out on this device.')

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })

  it('clears the session and displays a notification when logout request fails', async () => {
    const user = userEvent.setup()

    logoutMock.mockRejectedValueOnce(
      new Error('Internal server error'),
    )

    renderLayout()

    await user.click(
      screen.getByRole('button', { name: 'Open user menu' }),
    )

    await user.click(
      screen.getByRole('menuitem', { name: 'Sign out' }),
    )

    const dialog = screen.getByRole('alertdialog')

    await user.click(
      within(dialog).getByRole('button', { name: 'Sign out' }),
    )

    expect(
      await screen.findByRole('status'),
    ).toHaveTextContent(
      'You have been signed out on this device.',
    )

    expect(
      screen.queryByText('Internal server error'),
    ).not.toBeInTheDocument()
  })

  it('does not log out when confirmation is cancelled', async () => {
    const user = userEvent.setup()

    renderLayout()

    await user.click(
      screen.getByRole('button', { name: 'Sign out' }),
    )

    await user.click(
      screen.getByRole('button', { name: 'Stay signed in' }),
    )

    expect(logoutMock).not.toHaveBeenCalled()
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })

  it('navigates to the Compliance page when clicking the navigation link', async () => {
    const user = userEvent.setup()

    currentUser.role = 'HR_ADMIN'

    renderLayout()

    await user.click(
      screen.getByRole('link', { name: /compliance/i }),
    )

    expect(
      screen.getByText('Compliance page content'),
    ).toBeInTheDocument()
  })

  it('logs out from the sidebar after confirmation', async () => {
    const user = userEvent.setup()

    renderLayout()

    // Cliquer sur le bouton Sign out de la barre latérale
    const sidebar = screen.getByRole('navigation', {
      name: 'Main navigation',
    }).parentElement?.parentElement

    expect(sidebar).not.toBeNull()

    const sidebarSignOutButton = within(sidebar as HTMLElement).getByRole(
      'button',
      { name: 'Sign out' },
    )

    await user.click(sidebarSignOutButton)

    // Vérifier que la confirmation apparaît
    const dialog = screen.getByRole('alertdialog')

    expect(dialog).toBeInTheDocument()

    // Confirmer la déconnexion dans la boîte de dialogue
    await user.click(
      within(dialog).getByRole('button', { name: 'Sign out' }),
    )

    // Vérifier que logout est appelé
    await waitFor(() => {
      expect(logoutMock).toHaveBeenCalledTimes(1)
    })

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })
})
