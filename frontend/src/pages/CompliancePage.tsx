
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { getDashboard } from '../api/dashboardService'
import { getDepartments } from '../api/departmentService'
import { getSites } from '../api/siteService'

import StatCard from '../components/ui/StatCard'
import DataTable from '../components/ui/DataTable'
import Loading from '../components/ui/Loading'
import ErrorMessage from '../components/ui/ErrorMessage'

import type { TableColumn } from '../components/ui/DataTable'
import type { ComplianceMetrics } from '../api/dashboardService'

type ExpiringDocument = ComplianceMetrics['documents']['expired_details'][number]
type MissingDocuments = ComplianceMetrics['documents']['missing_documents_details'][number]
type IncompleteProfile = ComplianceMetrics['profiles']['incomplete_details'][number]
type RecentlyUploadedDocument =
  ComplianceMetrics['documents']['recently_uploaded_details'][number]

const formatPercentage = (value: number) =>
  `${Number(value).toFixed(1)}%`

const formatDate = (value: string) => {
  if (!value) return '—'

  const date = new Date(`${value}T00:00:00`)

  if (Number.isNaN(date.getTime())) return value

  return date.toLocaleDateString()
}

const expiredColumns: TableColumn<ExpiringDocument>[] = [
  {
    key: 'employee__user__name',
    header: 'Employee',
  },
  {
    key: 'document_type',
    header: 'Document type',
    render: (row) => (
      <Link
        to={`/documents/${row.id}`}
        className="font-medium text-blue-700 underline hover:text-blue-900"
      >
        {row.document_type}
      </Link>
    ),
  },
  {
    key: 'expires_at',
    header: 'Expiration date',
    render: (row) => formatDate(row.expires_at),
  },
]

const missingDocumentColumns: TableColumn<MissingDocuments>[] = [
  {
    key: 'employee_name',
    header: 'Employee',
  },
  {
    key: 'missing_document_types',
    header: 'Missing documents',
    render: (row) => row.missing_document_types.join(', '),
  },
]

const incompleteProfileColumns: TableColumn<IncompleteProfile>[] = [
  {
    key: 'user__name',
    header: 'Employee',
  },
  {
    key: 'department__name',
    header: 'Department',
  },
  {
    key: 'position__title',
    header: 'Position',
  },
]

const recentlyUploadedColumns: TableColumn<RecentlyUploadedDocument>[] = [
  {
    key: 'employee__user__name',
    header: 'Employee',
  },
  {
    key: 'document_type',
    header: 'Document type',
  },
  {
    key: 'status',
    header: 'Status',
  },
  {
    key: 'uploaded_at',
    header: 'Upload date',
    render: (row) => {
      const date = new Date(row.uploaded_at)

      return Number.isNaN(date.getTime())
        ? row.uploaded_at
        : date.toLocaleString()
    },
  },
]

export default function CompliancePage() {
  const { user } = useAuth()

  const [department, setDepartment] = useState<number | ''>('')
  const [site, setSite] = useState<number | ''>('')
  const [expirationDays, setExpirationDays] = useState<7 | 30 | 60 | 90>(30)
  const [uploadDays, setUploadDays] = useState<'' | 7 | 30 | 60 | 90>('')

  const canFilterDepartment =
    user?.role === 'HR_ADMIN' || user?.role === 'SUPER_ADMIN'

  const canFilterSite =
    user?.role === 'HR_ADMIN' ||
    user?.role === 'SUPER_ADMIN' ||
    user?.role === 'HR_MANAGER'

  const departmentsQuery = useQuery({
    queryKey: ['departments'],
    queryFn: getDepartments,
    enabled: canFilterDepartment,
  })

  const sitesQuery = useQuery({
    queryKey: ['sites'],
    queryFn: getSites,
    enabled: canFilterSite,
  })

  const dashboardQuery = useQuery({
    queryKey: [
      'compliance',
      department,
      site,
      expirationDays,
      uploadDays,
    ],
    queryFn: () =>
      getDashboard({
        ...(canFilterDepartment && department !== ''
          ? { department_id: department }
          : {}),
        ...(canFilterSite && site !== ''
          ? { site_id: site }
          : {}),
        expiring_within_days: expirationDays,
        ...(uploadDays !== ''
          ? { uploaded_within_days: uploadDays }
          : {}),
      }),
    enabled: user !== null && user?.role !== 'EMPLOYEE',
  })

  if (user?.role === 'EMPLOYEE') {
    return (
      <div className="mx-auto max-w-7xl space-y-4">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Compliance
        </h1>
        <p className="text-sm text-slate-500">
          Your account does not have access to HR compliance metrics.
        </p>
      </div>
    )
  }

  const compliance = dashboardQuery.data?.compliance

  const departmentOptions = departmentsQuery.data?.results ?? []

  const siteOptions = (sitesQuery.data?.results ?? []).filter(
    (item) =>
      item.is_active &&
      (department === '' || item.department === department),
  )

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <section>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Compliance
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Monitor employee profiles and required document compliance.
        </p>
      </section>

      {canFilterDepartment && (
        <section
          aria-label="Department filter"
          className="rounded-xl border border-slate-200 bg-white p-4"
        >
          <label
            htmlFor="compliance-department-filter"
            className="mb-1 block text-sm font-medium text-slate-700"
          >
            Department
          </label>

          <select
            id="compliance-department-filter"
            value={department}
            onChange={(event) => {
              setDepartment(
                event.target.value === ''
                  ? ''
                  : Number(event.target.value),
              )
              setSite('')
            }}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 sm:max-w-xs"
          >
            <option value="">All departments</option>
            {departmentOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>

          {departmentsQuery.isError && (
            <p role="alert" className="mt-2 text-sm text-red-600">
              Unable to load departments.
            </p>
          )}
        </section>
      )}

      {canFilterSite && (
        <section
          aria-label="Site filter"
          className="rounded-xl border border-slate-200 bg-white p-4"
        >
          <label
            htmlFor="compliance-site-filter"
            className="mb-1 block text-sm font-medium text-slate-700"
          >
            Site
          </label>

          <select
            id="compliance-site-filter"
            value={site}
            onChange={(event) =>
              setSite(
                event.target.value === ''
                  ? ''
                  : Number(event.target.value),
              )
            }
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 sm:max-w-xs"
          >
            <option value="">All sites</option>
            {siteOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} ({item.code})
              </option>
            ))}
          </select>

          {sitesQuery.isError && (
            <p role="alert" className="mt-2 text-sm text-red-600">
              Unable to load sites.
            </p>
          )}
        </section>
      )}

      <section
        aria-label="Document date filters"
        className="grid grid-cols-1 gap-4 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-2"
      >
        <div>
          <label
            htmlFor="compliance-expiration-filter"
            className="mb-1 block text-sm font-medium text-slate-700"
          >
            Upcoming expiration period
          </label>

          <select
            id="compliance-expiration-filter"
            value={expirationDays}
            onChange={(event) =>
              setExpirationDays(
                Number(event.target.value) as 7 | 30 | 60 | 90,
              )
            }
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          >
            <option value={7}>Next 7 days</option>
            <option value={30}>Next 30 days</option>
            <option value={60}>Next 60 days</option>
            <option value={90}>Next 90 days</option>
          </select>
        </div>

        <div>
          <label
            htmlFor="compliance-upload-filter"
            className="mb-1 block text-sm font-medium text-slate-700"
          >
            Recently uploaded documents
          </label>

          <select
            id="compliance-upload-filter"
            value={uploadDays}
            onChange={(event) =>
              setUploadDays(
                event.target.value === ''
                  ? ''
                  : (Number(event.target.value) as 7 | 30 | 60 | 90),
              )
            }
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          >
            <option value="">All time (disabled)</option>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={60}>Last 60 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
      </section>

      {dashboardQuery.isLoading ? (
        <Loading message="Loading compliance data..." />
      ) : dashboardQuery.isError || !compliance ? (
        <div className="space-y-4">
          <ErrorMessage message="Unable to load compliance data." />
          <button
            type="button"
            onClick={() => dashboardQuery.refetch()}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Retry
          </button>
        </div>
      ) : (
        <>
          <section
            aria-label="Compliance metrics"
            className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
          >
            <StatCard
              label="Profile completion"
              value={formatPercentage(compliance.profiles.completion_rate)}
              description={`${compliance.profiles.complete} complete profile(s)`}
              icon="👤"
            />

            <StatCard
              label="Document compliance"
              value={formatPercentage(compliance.documents.compliance_rate)}
              description={`${compliance.documents.compliant_employees} compliant employee(s)`}
              icon="📋"
            />

            <StatCard
              label="Expired documents"
              value={compliance.documents.expired_count}
              description="Document(s) past expiration date"
              icon="⚠️"
            />

            <StatCard
              label="Expiring soon"
              value={compliance.documents.expiring_soon_count}
              description={`Within the next ${expirationDays} days`}
              icon="📅"
            />
          </section>

          <section aria-label="Expired documents" className="space-y-3">
            <h2 className="text-lg font-semibold text-slate-900">
              Expired documents
            </h2>
            <DataTable
              columns={expiredColumns}
              data={compliance.documents.expired_details}
              rowKey={(row) => row.id}
              searchPlaceholder="Search expired documents..."
              emptyMessage="No expired documents."
            />
          </section>

          <section aria-label="Documents expiring soon" className="space-y-3">
            <h2 className="text-lg font-semibold text-slate-900">
              Documents expiring soon
            </h2>
            <DataTable
              columns={expiredColumns}
              data={compliance.documents.expiring_soon_details}
              rowKey={(row) => row.id}
              searchPlaceholder="Search upcoming expirations..."
              emptyMessage="No documents expiring soon."
            />
          </section>

          <section
            aria-label="Recently uploaded documents"
            className="space-y-3"
          >
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                Recently uploaded documents
              </h2>
              <p className="text-sm text-slate-500">
                {compliance.documents.recently_uploaded_count} document(s)
                uploaded in the selected period.
              </p>
            </div>

            <DataTable
              columns={recentlyUploadedColumns}
              data={compliance.documents.recently_uploaded_details}
              rowKey={(row) => row.id}
              searchPlaceholder="Search recently uploaded documents..."
              emptyMessage="No recently uploaded documents in this period."
            />
          </section>

          <section aria-label="Missing required documents" className="space-y-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                Missing required documents
              </h2>
              <p className="text-sm text-slate-500">
                {compliance.documents.employees_missing_required_documents} employee(s)
                missing required documents.
              </p>
            </div>
            <DataTable
              columns={missingDocumentColumns}
              data={compliance.documents.missing_documents_details}
              rowKey={(row) => row.employee_id}
              searchPlaceholder="Search missing documents..."
              emptyMessage="No missing required documents."
            />
          </section>

          <section aria-label="Incomplete employee profiles" className="space-y-3">
            <h2 className="text-lg font-semibold text-slate-900">
              Incomplete employee profiles
            </h2>
            <DataTable
              columns={incompleteProfileColumns}
              data={compliance.profiles.incomplete_details}
              rowKey={(row) => row.id}
              searchPlaceholder="Search incomplete profiles..."
              emptyMessage="No incomplete employee profiles."
            />
          </section>
        </>
      )}
    </div>
  )
}
