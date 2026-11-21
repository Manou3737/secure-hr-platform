
interface StatCardProps {
  label: string
  value: string | number
  description?: string
  icon?: string
}

export default function StatCard({
  label,
  value,
  description,
  icon,
}: StatCardProps) {
  return (
    <article className="group min-w-0 rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-md">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-slate-500">
            {label}
          </p>

          <p className="mt-3 break-words text-3xl font-bold tracking-tight text-slate-900">
            {value}
          </p>
        </div>

        {icon ? (
          <span
            aria-hidden="true"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-xl text-blue-700 transition-colors group-hover:bg-blue-100"
          >
            {icon}
          </span>
        ) : null}
      </div>

      {description ? (
        <p className="mt-3 text-xs leading-relaxed text-slate-500">
          {description}
        </p>
      ) : null}
    </article>
  )
}
