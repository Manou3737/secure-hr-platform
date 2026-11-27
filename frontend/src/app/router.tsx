import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import ProtectedRoute from '../auth/ProtectedRoute'
import AppLayout from '../components/layout/AppLayout'

const LoginPage = lazy(() => import('../pages/LoginPage'))
const DashboardPage = lazy(() => import('../pages/DashboardPage'))
const EmployeesPage = lazy(() => import('../pages/EmployeesPage'))
const EmployeeDetailPage = lazy(
  () => import('../pages/EmployeeDetailPage'),
)
const ModulePage = lazy(() => import('../pages/ModulePage'))
const ProfilePage = lazy(() => import('../pages/ProfilePage'))
const CompliancePage = lazy(() => import('../pages/CompliancePage'))
const DocumentsPage = lazy(() => import('../pages/DocumentsPage'))
const TasksPage = lazy(() => import('../pages/TasksPage'))

const DocumentDetailPage = lazy(
  () => import('../pages/DocumentDetailPage'),
)
const TaskDetailPage = lazy(
  () => import('../pages/TaskDetailPage'),
)
const HR_ROLES = ['SUPER_ADMIN', 'HR_ADMIN', 'HR_MANAGER'] as const

export default function AppRouter() {
  return (
    <Suspense
      fallback={
        <div role="status" className="p-6 text-sm text-slate-500">
          Loading page...
        </div>
      }
    >
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/profile" element={<ProfilePage />} />

            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/documents/:id" element={<DocumentDetailPage />} />

            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/tasks/:id" element={<TaskDetailPage />} />

            <Route element={<ProtectedRoute roles={[...HR_ROLES]} />}>
              <Route path="/employees" element={<EmployeesPage />} />

              <Route
                path="/employees/:id"
                element={<EmployeeDetailPage />}
              />
              <Route path="/recruitment" element={<ModulePage title="Recruitment" />} />

              <Route path="/bank-accounts" element={<ModulePage title="Bank Accounts" />} />
              <Route path="/compliance" element={<CompliancePage />} />
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
    </Suspense>
  )
}
