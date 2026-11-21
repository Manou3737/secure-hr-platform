
import type { ChangeEvent } from 'react'

export interface FilterOption {
  label: string
  value: string
}

export interface FilterConfig {
  key: string
  label: string
  options: FilterOption[]
}

interface FilterBarProps {
  filters: FilterConfig[]
  values: Record<string, string>
  onChange: (key: string, value: string) => void
  onReset: () => void
}

export default function FilterBar({
  filters,
  values,
  onChange,
  onReset,
}: FilterBarProps) {
  const hasActiveFilters = Object.values(values).some(Boolean)

  return (
    <section className="grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-3">
      {filters.map((filter) => (
        <div key={filter.key} className="min-w-0">
          <label
            htmlFor={`filter-${filter.key}`}
            className="mb-1.5 block text-xs font-semibold text-slate-600"
          >
            {filter.label}
          </label>

          <select
            id={`filter-${filter.key}`}
            value={values[filter.key] ?? ''}
            onChange={(event: ChangeEvent<HTMLSelectElement>) =>
              onChange(filter.key, event.target.value)
            }
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          >
            <option value="">All</option>

            {filter.options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      ))}

      <button
        type="button"
        disabled={!hasActiveFilters}
        onClick={onReset}
        className="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40 sm:w-auto"
      >
        Reset filters
      </button>
    </section>
  )
}
