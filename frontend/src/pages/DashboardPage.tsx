import { useQuery } from '@tanstack/react-query'

import { useAuth } from '../auth/useAuth'
import { getDashboard } from '../api/dashboardService'
import StatCard from '../components/ui/StatCard'

export default function DashboardPage() {
  const { user } = useAuth()

  const {
  data,
  isLoading,
  isError,
  refetch,
} = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboard,
    enabled: user?.role !== 'EMPLOYEE',
  })

  const openPositions =
    data?.recruitment.job_postings.by_status
      .filter((item) => item.status === 'OPEN')
      .reduce((total, item) => total + item.count, 0) ?? 0

  const pendingDocuments = data
    ? data.risk.document_lifecycle.pending_scan +
      data.risk.document_lifecycle.pending_review
    : 0

  if (user?.role === 'EMPLOYEE') {
    return (
      <div className="mx-auto max-w-7xl space-y-4">
        <h1 className="text-2xl font-bold text-slate-900">
          Welcome back, {user.name}
        </h1>
        <p className="text-sm text-slate-500">
          Your account does not have access to HR dashboard metrics.
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <section>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Welcome back, {user?.name}
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Here is an overview of your HR workspace.
        </p>
      </section>

      {isLoading && (
        <p role="status" className="text-sm text-slate-500">
          Loading dashboard metrics...
        </p>
      )}

      {isError && (
        <div
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 p-4"
        >
          <p className="text-sm text-red-700">
            Unable to load dashboard metrics. Please try again.
          </p>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-2 text-sm font-semibold text-red-700 underline"
          >
            Try again
          </button>
        </div>
      )}

      {data && (
        <section
          aria-label="HR statistics"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
        >
          <StatCard
            label="Employees"
            value={data.workforce.headcount.total}
            description="Total workforce"
            icon="👥"
          />

          <StatCard
            label="Active Accounts"
            value={data.workforce.headcount.active_accounts}
            description="Active employee accounts"
            icon="✓"
          />

          <StatCard
            label="Open Positions"
            value={openPositions}
            description="Currently open job postings"
            icon="💼"
          />

          <StatCard
            label="Pending Documents"
            value={pendingDocuments}
            description="Awaiting scan or review"
            icon="📄"
          />
        </section>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-slate-900">
          Account information
        </h2>

        <dl className="mt-5 grid gap-5 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-slate-500">Email</dt>
            <dd className="mt-1 break-all font-medium text-slate-900">
              {user?.email}
            </dd>
          </div>

          <div>
            <dt className="text-slate-500">Role</dt>
            <dd className="mt-1 break-all font-medium text-slate-900">
              {user?.role.replaceAll('_', ' ')}
            </dd>
          </div>

          <div>
            <dt className="text-slate-500">Email verified</dt>
            <dd className="mt-1 break-all font-medium text-slate-900">
              {user?.email_verified ? 'Yes' : 'No'}
            </dd>
          </div>
        </dl>
      </section>
    </div>
  )
}
