
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { useAuth } from '../auth/useAuth'
import { getDashboard } from '../api/dashboardService'
import { getDepartments } from '../api/departmentService'

import StatCard from '../components/ui/StatCard'
import WorkforceOverview from '../features/dashboard/components/WorkforceOverview'
import RecruitmentCharts from '../features/dashboard/components/RecruitmentCharts'
import ComplianceOverview from '../features/dashboard/components/ComplianceOverview'
import OnboardingOverview from '../features/dashboard/components/OnboardingOverview'
import OperationsOverview from '../features/dashboard/components/OperationsOverview'
import SecurityOverview from '../features/dashboard/components/SecurityOverview'
import AuditOverview from '../features/dashboard/components/AuditOverview'
import RiskOverview from '../features/dashboard/components/RiskOverview'

const PERIOD_OPTIONS = [
  { value: 7, label: 'Last 7 days' },
  { value: 30, label: 'Last 30 days' },
  { value: 90, label: 'Last 90 days' },
  { value: 365, label: 'Last 365 days' },
]

export default function DashboardPage() {
  const { user } = useAuth()

  const [days, setDays] = useState(7)
  const [department, setDepartment] = useState<number | ''>('')

  const canFilterDepartment =
    user?.role === 'HR_ADMIN' || user?.role === 'SUPER_ADMIN'

  const departmentsQuery = useQuery({
    queryKey: ['departments'],
    queryFn: getDepartments,
    enabled: canFilterDepartment,
  })

  const {
    data,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['dashboard', days, department],
    queryFn: () =>
      getDashboard({
        days,
        ...(canFilterDepartment && department !== ''
          ? { department_id: department }
          : {}),
      }),
    enabled: user !== null && user?.role !== 'EMPLOYEE',
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

      <section
        aria-label="Dashboard filters"
        className="grid grid-cols-1 gap-4 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2"
      >
        <div>
          <label
            htmlFor="dashboard-period-filter"
            className="mb-1 block text-sm font-medium text-slate-700"
          >
            Filter by period
          </label>
          <select
            id="dashboard-period-filter"
            value={days}
            onChange={(event) => setDays(Number(event.target.value))}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            {PERIOD_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {canFilterDepartment && (
          <div>
            <label
              htmlFor="dashboard-department-filter"
              className="mb-1 block text-sm font-medium text-slate-700"
            >
              Filter by department
            </label>
            <select
              id="dashboard-department-filter"
              value={department}
              onChange={(event) =>
                setDepartment(
                  event.target.value === ''
                    ? ''
                    : Number(event.target.value),
                )
              }
              disabled={
                departmentsQuery.isLoading ||
                departmentsQuery.isError
              }
              aria-describedby={
                departmentsQuery.isLoading
                  ? 'dashboard-departments-loading'
                  : undefined
              }
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:cursor-not-allowed disabled:bg-slate-100"
            >
              <option value="">All departments</option>
              {departmentsQuery.data?.results.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>

            {departmentsQuery.isLoading && (
              <p
                id="dashboard-departments-loading"
                role="status"
                className="mt-1 text-xs text-slate-500"
              >
                Loading departments...
              </p>
            )}

            {departmentsQuery.isError && (
              <div className="mt-2 space-y-2">
                <p role="alert" className="text-xs text-red-700">
                  Unable to load departments.
                </p>
                <button
                  type="button"
                  onClick={() => departmentsQuery.refetch()}
                  className="text-sm font-semibold text-red-700 underline"
                >
                  Retry departments
                </button>
              </div>
            )}
          </div>
        )}
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
        <>
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

          <WorkforceOverview data={data.workforce} />
          <ComplianceOverview data={data.compliance} />
          <OnboardingOverview data={data.onboarding} />
          <OperationsOverview data={data.operations} />
          <SecurityOverview data={data.security} />
          <AuditOverview data={data.audit} />
          <RiskOverview data={data.risk} />
          <RecruitmentCharts data={data.recruitment} />
        </>
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
