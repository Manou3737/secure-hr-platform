
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { getEmployeeById } from '../api/employeeService'
import { getDepartments } from '../api/departmentService'
import { getPositions } from '../api/positionService'

import Loading from '../components/ui/Loading'
import ErrorMessage from '../components/ui/ErrorMessage'

export default function EmployeeDetailPage() {
  const { id } = useParams()

  const employeeId = Number(id)
  const isValidId =
    id !== undefined &&
    /^\d+$/.test(id) &&
    Number.isSafeInteger(employeeId) &&
    employeeId > 0

  const employeeQuery = useQuery({
    queryKey: ['employee', employeeId],
    queryFn: () => getEmployeeById(employeeId),
    enabled: isValidId,
  })

  const employee = employeeQuery.data

  const departmentsQuery = useQuery({
    queryKey: ['departments'],
    queryFn: getDepartments,
    enabled: employee !== undefined,
  })

  const positionsQuery = useQuery({
    queryKey: ['positions', employee?.department],
    queryFn: () => getPositions(employee!.department),
    enabled: employee !== undefined,
  })

  if (!isValidId) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <ErrorMessage message="Invalid employee ID." />
        <Link
          to="/employees"
          className="text-sm font-semibold text-blue-700 hover:underline"
        >
          Back to employees
        </Link>
      </div>
    )
  }

  if (employeeQuery.isLoading) {
    return <Loading message="Loading employee details..." />
  }

  if (employeeQuery.isError || !employee) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <ErrorMessage message="Unable to load this employee record." />

        <button
          type="button"
          onClick={() => employeeQuery.refetch()}
          className="text-sm font-semibold text-blue-700 hover:underline"
        >
          Retry
        </button>

        <div>
          <Link
            to="/employees"
            className="text-sm font-semibold text-blue-700 hover:underline"
          >
            Back to employees
          </Link>
        </div>
      </div>
    )
  }

  if (departmentsQuery.isLoading || positionsQuery.isLoading) {
    return <Loading message="Loading employee information..." />
  }

  const department = departmentsQuery.data?.results.find(
    (item) => item.id === employee.department,
  )

  const position = positionsQuery.data?.results.find(
    (item) => item.id === employee.position,
  )

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <Link
          to="/employees"
          className="text-sm font-semibold text-blue-700 hover:underline"
        >
          ← Back to employees
        </Link>

        <h1 className="mt-4 text-2xl font-bold tracking-tight text-slate-900">
          Employee details
        </h1>

        <p className="mt-1 text-sm text-slate-500">
          Employee ID: {employee.employee_id}
        </p>
      </div>

      {departmentsQuery.isError && (
        <ErrorMessage message="Department information could not be loaded. Showing its ID instead." />
      )}

      {positionsQuery.isError && (
        <ErrorMessage message="Position information could not be loaded. Showing its ID instead." />
      )}

      <section
        aria-label="Employee information"
        className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <h2 className="border-b border-slate-100 pb-4 text-lg font-semibold text-slate-900">
          Professional information
        </h2>

        <div className="grid gap-6 pt-6 sm:grid-cols-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Employee ID
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {employee.employee_id}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              User ID
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {employee.user}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Department
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {department?.name ?? `Department #${employee.department}`}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Position
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {position?.title ?? `Position #${employee.position}`}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Hire date
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {employee.hire_date}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Record created
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {new Date(employee.created_at).toLocaleString()}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Last updated
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {new Date(employee.updated_at).toLocaleString()}
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
