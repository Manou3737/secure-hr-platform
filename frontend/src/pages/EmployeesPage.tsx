import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { getEmployees } from '../api/employeeService'
import type { EmployeeProfile } from '../api/employeeService'
import { getDepartments } from '../api/departmentService'
import { getPositions } from '../api/positionService'

import DataTable from '../components/ui/DataTable'
import type { TableColumn } from '../components/ui/DataTable'
import Loading from '../components/ui/Loading'
import ErrorMessage from '../components/ui/ErrorMessage'

const PAGE_SIZE = 20

export default function EmployeesPage() {
  const [page, setPage] = useState(1)
  const [hireDate, setHireDate] = useState('')
  const [search, setSearch] = useState('')
  const [department, setDepartment] = useState<number | ''>('')
  const [position, setPosition] = useState<number | ''>('')

  const departmentsQuery = useQuery({
    queryKey: ['departments'],
    queryFn: getDepartments,
  })

  const positionsQuery = useQuery({
    queryKey: ['positions', department],
    queryFn: () => getPositions(department as number),
    enabled: department !== '',
  })

  const {
    data,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: [
      'employees',
      page,
      hireDate,
      search,
      department,
      position,
    ],
    queryFn: () =>
      getEmployees({
        page,
        page_size: PAGE_SIZE,
        ...(hireDate ? { hire_date: hireDate } : {}),
        ...(search.trim() ? { search: search.trim() } : {}),
        ...(department !== '' ? { department } : {}),
        ...(position !== '' ? { position } : {}),
      }),
  })

  function handleHireDateChange(value: string) {
    setHireDate(value)
    setPage(1)
  }

  function handleSearchChange(value: string) {
    setSearch(value)
    setPage(1)
  }

  function handleDepartmentChange(value: string) {
    setDepartment(value === '' ? '' : Number(value))
    setPosition('')
    setPage(1)
  }

  function handlePositionChange(value: string) {
    setPosition(value === '' ? '' : Number(value))
    setPage(1)
  }

  function clearFilters() {
    setHireDate('')
    setSearch('')
    setDepartment('')
    setPosition('')
    setPage(1)
  }

  const columns: TableColumn<EmployeeProfile>[] = [
    {
      key: 'employee_id',
      header: 'Employee ID',
      render: (employee) => employee.employee_id,
    },
    {
      key: 'user',
      header: 'User ID',
      render: (employee) => employee.user,
    },
    {
      key: 'department',
      header: 'Department ID',
      render: (employee) => employee.department,
    },
    {
      key: 'position',
      header: 'Position ID',
      render: (employee) => employee.position,
    },
    {
      key: 'hire_date',
      header: 'Hire date',
      render: (employee) => employee.hire_date,
    },
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">
          Employees
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Manage and review employee records.
        </p>
      </div>

      <section
        aria-label="Employee filters"
        className="grid grid-cols-1 gap-4 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        <div>
          <label
            htmlFor="employee-search"
            className="mb-1 block text-sm font-medium text-slate-700"
          >
            Search employees
          </label>
          <input
            id="employee-search"
            type="search"
            value={search}
            onChange={(event) => handleSearchChange(event.target.value)}
            placeholder="Search..."
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label
            htmlFor="hire-date-filter"
            className="mb-1 block text-sm font-medium text-slate-700"
          >
            Filter by hire date
          </label>
          <input
            id="hire-date-filter"
            type="date"
            value={hireDate}
            onChange={(event) => handleHireDateChange(event.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label
            htmlFor="department-filter"
            className="mb-1 block text-sm font-medium text-slate-700"
          >
            Filter by department
          </label>
          <select
            id="department-filter"
            value={department}
            onChange={(event) => handleDepartmentChange(event.target.value)}
            disabled={departmentsQuery.isLoading}
            aria-describedby={
              departmentsQuery.isLoading
                ? 'departments-loading'
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
              id="departments-loading"
              role="status"
              className="mt-1 text-xs text-slate-500"
            >
              Loading departments...
            </p>
          )}

          {departmentsQuery.isError && (
            <div className="mt-2 space-y-2">
              <ErrorMessage message="Unable to load departments. Please try again." />
              <button
                type="button"
                onClick={() => departmentsQuery.refetch()}
                className="text-sm font-semibold text-red-700 underline"
              >
                Retry departments
              </button>
            </div>
          )}

          {departmentsQuery.isSuccess &&
            departmentsQuery.data.results.length === 0 && (
              <p className="mt-1 text-xs text-slate-500">
                No departments available.
              </p>
            )}
        </div>

        <div>
          <label
            htmlFor="position-filter"
            className="mb-1 block text-sm font-medium text-slate-700"
          >
            Filter by position
          </label>
          <select
            id="position-filter"
            value={position}
            onChange={(event) => handlePositionChange(event.target.value)}
            disabled={
              department === '' ||
              positionsQuery.isLoading ||
              positionsQuery.isError
            }
            aria-describedby={
              positionsQuery.isLoading
                ? 'positions-loading'
                : undefined
            }
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:cursor-not-allowed disabled:bg-slate-100"
          >
            <option value="">All positions</option>
            {positionsQuery.data?.results.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </select>

          {department !== '' && positionsQuery.isLoading && (
            <p
              id="positions-loading"
              role="status"
              className="mt-1 text-xs text-slate-500"
            >
              Loading positions...
            </p>
          )}

          {department !== '' && positionsQuery.isError && (
            <div className="mt-2 space-y-2">
              <ErrorMessage message="Unable to load positions. Please try again." />
              <button
                type="button"
                onClick={() => positionsQuery.refetch()}
                className="text-sm font-semibold text-red-700 underline"
              >
                Retry positions
              </button>
            </div>
          )}

          {department !== '' &&
            positionsQuery.isSuccess &&
            positionsQuery.data.results.length === 0 && (
              <p className="mt-1 text-xs text-slate-500">
                No positions available for this department.
              </p>
            )}
        </div>
      </section>

      {(search || hireDate || department !== '' || position !== '') && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={clearFilters}
            className="text-sm font-medium text-blue-700 underline hover:text-blue-900"
          >
            Clear all filters
          </button>
        </div>
      )}

      {isLoading && <Loading message="Loading employees..." />}

      {isError && (
        <div className="space-y-3">
          <ErrorMessage message="Unable to load employees. Please try again." />
          <button
            type="button"
            onClick={() => refetch()}
            className="text-sm font-semibold text-red-700 underline"
          >
            Try again
          </button>
        </div>
      )}

      {data && !isError && (
        <DataTable<EmployeeProfile>
          columns={columns}
          data={data.results}
          rowKey={(employee) => employee.id}
          emptyMessage="No employees found."
          pageSize={PAGE_SIZE}
          serverPagination={{
            page,
            totalCount: data.count,
            onPageChange: setPage,
          }}
        />
      )}
    </div>
  )
}
