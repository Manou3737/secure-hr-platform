import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'

export interface TableColumn<T> {
  key: string
  header: string
  render?: (row: T) => ReactNode
}

export interface ServerPagination {
  page: number
  totalCount: number
  onPageChange: (page: number) => void
}

interface DataTableProps<T> {
  columns: TableColumn<T>[]
  data: T[]
  rowKey: (row: T) => string | number
  searchPlaceholder?: string
  emptyMessage?: string
  pageSize?: number
  serverPagination?: ServerPagination
}

const DEFAULT_PAGE_SIZE = 10

function normalizePageSize(value: number): number {
  if (!Number.isFinite(value) || value <= 0) {
    return DEFAULT_PAGE_SIZE
  }

  return Math.max(1, Math.floor(value))
}

export default function DataTable<T extends object>({
  columns,
  data,
  rowKey,
  searchPlaceholder = 'Search...',
  emptyMessage = 'No records found.',
  pageSize = DEFAULT_PAGE_SIZE,
  serverPagination,
}: DataTableProps<T>) {
  const [search, setSearch] = useState('')
  const [currentPage, setCurrentPage] = useState(1)

  const safePageSize = normalizePageSize(pageSize)
  const isServerPaginated = Boolean(serverPagination)

  const filteredData = useMemo(() => {
    const query = search.trim().toLowerCase()

    if (!query) return data

    return data.filter((row) =>
      Object.values(row).some((value) => {
        if (
          value === null ||
          value === undefined ||
          typeof value === 'object'
        ) {
          return false
        }

        return String(value).toLowerCase().includes(query)
      }),
    )
  }, [data, search])

  const rawTotalCount = serverPagination
    ? serverPagination.totalCount
    : filteredData.length

  const totalCount = Number.isFinite(rawTotalCount)
    ? Math.max(0, Math.floor(rawTotalCount))
    : 0

  const totalPages = Math.max(
    1,
    Math.ceil(totalCount / safePageSize),
  )

  const requestedPage = serverPagination
    ? serverPagination.page
    : currentPage

  const normalizedPage =
    Number.isFinite(requestedPage) && requestedPage > 0
      ? Math.floor(requestedPage)
      : 1

  const safePage = Math.min(normalizedPage, totalPages)

  const displayedData = serverPagination
    ? data
    : filteredData.slice(
        (safePage - 1) * safePageSize,
        safePage * safePageSize,
      )

  const startRecord =
    totalCount === 0
      ? 0
      : (safePage - 1) * safePageSize + 1

  const endRecord = Math.min(
    safePage * safePageSize,
    totalCount,
  )

  function getCellValue(row: T, key: string) {
    const value = (row as Record<string, unknown>)[key]

    return value === null || value === undefined
      ? '—'
      : String(value)
  }

  function goToPage(page: number) {
    const targetPage = Math.max(
      1,
      Math.min(Math.floor(page), totalPages),
    )

    if (serverPagination) {
      serverPagination.onPageChange(targetPage)
    } else {
      setCurrentPage(targetPage)
    }
  }

  return (
    <section
      aria-label="Data table"
      className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
    >
      <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">
            Records
          </h2>

          <p
            className="mt-1 text-xs text-slate-500"
            aria-live="polite"
            aria-atomic="true"
          >
            {totalCount} record(s) found
          </p>
        </div>

        {!isServerPaginated && (
          <input
            type="search"
            aria-label="Search records"
            placeholder={searchPlaceholder}
            value={search}
            onChange={(event) => {
              setSearch(event.target.value)
              setCurrentPage(1)
            }}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 sm:max-w-xs"
          />
        )}
      </div>

      <div className="w-full overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <caption className="sr-only">
            Records table
          </caption>

          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  className="whitespace-nowrap px-5 py-3 font-semibold"
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-100">
            {displayedData.length > 0 ? (
              displayedData.map((row) => (
                <tr
                  key={rowKey(row)}
                  className="transition-colors hover:bg-slate-50"
                >
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className="whitespace-nowrap px-5 py-4 text-slate-700"
                    >
                      {column.render
                        ? column.render(row)
                        : getCellValue(row, column.key)}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td
                  colSpan={Math.max(columns.length, 1)}
                  className="px-5 py-12 text-center text-sm text-slate-500"
                >
                  {emptyMessage}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-col gap-3 border-t border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <p
          className="text-xs text-slate-500"
          aria-live="polite"
          aria-atomic="true"
        >
          Showing {startRecord} to {endRecord} of {totalCount} records
        </p>

        <nav
          aria-label="Table pagination"
          className="flex items-center gap-2"
        >
          <button
            type="button"
            disabled={safePage <= 1}
            onClick={() => goToPage(safePage - 1)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Previous
          </button>

          <span
            className="text-xs text-slate-600"
            role="status"
            aria-label={`Page ${safePage} of ${totalPages}`}
          >
            Page {safePage} of {totalPages}
          </span>

          <button
            type="button"
            disabled={safePage >= totalPages}
            onClick={() => goToPage(safePage + 1)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Next
          </button>
        </nav>
      </div>
    </section>
  )
}
