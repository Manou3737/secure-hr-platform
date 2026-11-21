
import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/useAuth'
import Button from '../ui/Button'
import ConfirmDialog from '../ui/ConfirmDialog'
import { useToast } from '../ui/useToast'

type NavigationItem = {
  label: string
  path: string
  icon: string
  roles: string[]
}

const navigation: NavigationItem[] = [
  {
    label: 'Dashboard',
    path: '/dashboard',
    icon: '▦',
    roles: [],
  },
  {
    label: 'Employees',
    path: '/employees',
    icon: '♙',
    roles: ['SUPER_ADMIN', 'HR_ADMIN', 'HR_MANAGER'],
  },
  {
    label: 'Recruitment',
    path: '/recruitment',
    icon: '◎',
    roles: ['SUPER_ADMIN', 'HR_ADMIN', 'HR_MANAGER'],
  },
  {
    label: 'HR Documents',
    path: '/documents',
    icon: '▤',
    roles: ['SUPER_ADMIN', 'HR_ADMIN', 'HR_MANAGER'],
  },
  {
    label: 'Bank Accounts',
    path: '/bank-accounts',
    icon: '▣',
    roles: ['SUPER_ADMIN', 'HR_ADMIN', 'HR_MANAGER'],
  },
  {
    label: 'Leave Requests',
    path: '/leave-requests',
    icon: '◷',
    roles: [],
  },
]

const pageTitles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/employees': 'Employees',
  '/recruitment': 'Recruitment',
  '/documents': 'HR Documents',
  '/bank-accounts': 'Bank Accounts',
  '/leave-requests': 'Leave Requests',
  '/profile': 'My Profile',
}

function formatRole(role?: string) {
  return role?.replaceAll('_', ' ') || 'User'
}

function getInitials(name?: string) {
  if (!name?.trim()) return 'U'

  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join('')
}

export default function AppLayout() {
  const { user, logout } = useAuth()
  const { showToast } = useToast()
  const location = useLocation()
  const navigate = useNavigate()

  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [logoutDialogOpen, setLogoutDialogOpen] = useState(false)

  const userMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        userMenuRef.current &&
        !userMenuRef.current.contains(event.target as Node)
      ) {
        setUserMenuOpen(false)
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setUserMenuOpen(false)
        setSidebarOpen(false)
      }
    }

    function handlePopState() {
      setSidebarOpen(false)
      setUserMenuOpen(false)
    }

    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleEscape)
    window.addEventListener('popstate', handlePopState)

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
      window.removeEventListener('popstate', handlePopState)
    }
  }, [])

  const currentTitle = pageTitles[location.pathname] ?? 'Dashboard'

  const visibleNavigation = navigation.filter(
    (item) =>
      item.roles.length === 0 ||
      item.roles.includes(user?.role ?? ''),
  )

  function requestLogout() {
    setUserMenuOpen(false)
    setSidebarOpen(false)
    setLogoutDialogOpen(true)
  }

  async function handleLogout() {
    try {
      await logout()
    } catch {
      // AuthProvider handles local session cleanup.
    }

    showToast('You have been signed out on this device.', 'info')
  }

  function navigateToProfile() {
    setUserMenuOpen(false)
    setSidebarOpen(false)
    navigate('/profile')
  }

  return (
    <div className="flex min-h-dvh bg-hr-background text-slate-800">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-40 bg-slate-950/60 backdrop-blur-[2px] lg:hidden"
        />
      )}

      {/* Sidebar */}
      <aside
        id="app-sidebar"
        aria-label="Application sidebar"
        className={`fixed inset-y-0 left-0 z-50 flex h-dvh w-64 flex-col border-r border-white/5 bg-hr-sidebar text-white shadow-xl transition-transform duration-200 ease-out lg:sticky lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand */}
        <div className="flex h-16 shrink-0 items-center border-b border-white/10 px-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-sm font-extrabold tracking-tight shadow-lg shadow-blue-950/30">
            HR
          </div>

          <div className="ml-3 min-w-0">
            <p className="truncate text-sm font-bold tracking-wide text-white">
              Secure HR
            </p>
            <p className="truncate text-[11px] text-slate-400">
              Management Platform
            </p>
          </div>
        </div>

        {/* Workspace navigation */}
        <div className="flex-1 overflow-y-auto px-3 py-6">
          <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
            Workspace
          </p>

          <nav
            aria-label="Main navigation"
            className="space-y-1"
          >
            {visibleNavigation.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) =>
                  `group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium transition-all duration-150 ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-md shadow-blue-950/20'
                      : 'text-slate-300 hover:bg-hr-sidebar-hover hover:text-white'
                  }`
                }
              >
                <span
                  aria-hidden="true"
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-base transition-colors"
                >
                  {item.icon}
                </span>

                <span className="truncate">{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Sidebar user section */}
        <div className="border-t border-white/10 p-4">
          <div className="mb-4 flex items-center gap-3 rounded-xl bg-white/5 p-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-700 text-xs font-bold text-white ring-1 ring-white/10">
              {getInitials(user?.name)}
            </div>

            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-semibold text-slate-100">
                {user?.name || 'User'}
              </p>
              <p className="truncate text-[10px] capitalize text-slate-400">
                {formatRole(user?.role)}
              </p>
            </div>
          </div>

          <Button
            variant="secondary"
            className="w-full"
            onClick={requestLogout}
          >
            Sign out
          </Button>
        </div>
      </aside>

      {/* Main application */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Topbar */}
        <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center justify-between border-b border-slate-200/80 bg-white/95 px-4 backdrop-blur sm:px-6">
          {/* Page title and breadcrumb */}
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              aria-label="Open navigation"
              aria-expanded={sidebarOpen}
              aria-controls="app-sidebar"
              onClick={() => setSidebarOpen(true)}
              className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 lg:hidden"
            >
              <span aria-hidden="true">☰</span>
            </button>

            <div className="min-w-0">
              <h1 className="truncate text-sm font-bold text-slate-800 sm:text-base">
                {currentTitle}
              </h1>

              <nav
                aria-label="Breadcrumb"
                className="hidden sm:block"
              >
                <ol className="flex items-center gap-2 text-[11px] text-slate-500">
                  <li>Workspace</li>
                  <li aria-hidden="true" className="text-slate-300">
                    /
                  </li>
                  <li
                    aria-current="page"
                    className="font-medium text-blue-700"
                  >
                    {currentTitle}
                  </li>
                </ol>
              </nav>
            </div>
          </div>

          {/* User menu */}
          <div
            className="relative ml-3"
            ref={userMenuRef}
          >
            <button
              type="button"
              onClick={() => setUserMenuOpen((open) => !open)}
              aria-expanded={userMenuOpen}
              aria-haspopup="true"
              aria-label="Open user menu"
              className="flex items-center gap-2 rounded-xl px-2 py-1.5 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 sm:gap-3 sm:px-3"
            >
              <div className="hidden text-right sm:block">
                <p className="max-w-40 truncate text-xs font-semibold text-slate-800">
                  {user?.name}
                </p>
                <p className="text-[10px] text-slate-500">
                  {formatRole(user?.role)}
                </p>
              </div>

              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-50 text-xs font-bold text-blue-700 ring-1 ring-blue-100">
                {getInitials(user?.name)}
              </div>

              <span
                aria-hidden="true"
                className="text-[10px] text-slate-400"
              >
                ▼
              </span>
            </button>

            {userMenuOpen && (
              <div
                role="menu"
                className="absolute right-0 mt-2 w-64 max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-slate-200 bg-white py-1.5 shadow-xl shadow-slate-900/10"
              >
                {/* Account details */}
                <div className="border-b border-slate-100 px-4 py-3">
                  <p className="truncate text-sm font-semibold text-slate-900">
                    {user?.name}
                  </p>

                  <p className="truncate text-xs text-slate-500">
                    {user?.email}
                  </p>

                  <p className="mt-1.5 text-[11px] font-semibold text-blue-700">
                    {formatRole(user?.role)}
                  </p>
                </div>

                <button
                  type="button"
                  role="menuitem"
                  onClick={navigateToProfile}
                  className="w-full px-4 py-2.5 text-left text-xs font-medium text-slate-700 transition hover:bg-slate-50"
                >
                  My Profile
                </button>

                <div className="mx-3 border-t border-slate-100" />

                <button
                  type="button"
                  role="menuitem"
                  onClick={requestLogout}
                  className="w-full px-4 py-2.5 text-left text-xs font-semibold text-red-600 transition hover:bg-red-50"
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="w-full min-w-0 flex-1 p-4 sm:p-6 lg:p-8">
          <div className="mx-auto w-full max-w-[1600px]">
            <Outlet />
          </div>
        </main>
      </div>

      {/* Logout confirmation */}
      <ConfirmDialog
        open={logoutDialogOpen}
        title="Confirm sign out"
        message="Are you sure you want to sign out of your account?"
        confirmLabel="Sign out"
        cancelLabel="Stay signed in"
        variant="danger"
        onCancel={() => setLogoutDialogOpen(false)}
        onConfirm={() => {
          setLogoutDialogOpen(false)
          void handleLogout()
        }}
      />
    </div>
  )
}
