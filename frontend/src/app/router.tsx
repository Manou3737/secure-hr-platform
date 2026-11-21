import { Navigate, Route, Routes } from 'react-router-dom'

import ProtectedRoute from '../auth/ProtectedRoute'
import AppLayout from '../components/layout/AppLayout'
import LoginPage from '../pages/LoginPage'
import DashboardPage from '../pages/DashboardPage'
import EmployeesPage from '../pages/EmployeesPage'
import ModulePage from '../pages/ModulePage'
import ProfilePage from '../pages/ProfilePage'

const HR_ROLES = ['SUPER_ADMIN', 'HR_ADMIN', 'HR_MANAGER'] as const

export default function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route element={<ProtectedRoute roles={[...HR_ROLES]} />}>
            <Route
              path="/employees"
              element={<EmployeesPage />}
            />
            <Route
              path="/recruitment"
              element={<ModulePage title="Recruitment" />}
            />
            <Route
              path="/documents"
              element={<ModulePage title="HR Documents" />}
            />
            <Route
              path="/bank-accounts"
              element={<ModulePage title="Bank Accounts" />}
            />
          </Route>

          <Route
            path="/leave-requests"
            element={<ModulePage title="Leave Requests" />}
          />
        </Route>
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
