import { Navigate, Outlet } from 'react-router-dom'
import type { AuthUser } from './authService'
import { useAuth } from './useAuth'
import Loading from '../components/ui/Loading'

interface ProtectedRouteProps {
  roles?: AuthUser['role'][]
}

export default function ProtectedRoute({ roles }: ProtectedRouteProps) {
  const { user, isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <Loading message="Checking authentication..." />
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (roles && (!user || !roles.includes(user.role))) {
    return <Navigate to="/dashboard" replace />
  }

  return <Outlet />
}
