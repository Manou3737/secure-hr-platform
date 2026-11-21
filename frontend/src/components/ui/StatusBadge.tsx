
interface StatusBadgeProps {
  status: string
}

const statusStyles: Record<string, string> = {
  ACTIVE: 'bg-green-50 text-green-700 ring-green-600/20',
  VERIFIED: 'bg-green-50 text-green-700 ring-green-600/20',
  APPROVED: 'bg-green-50 text-green-700 ring-green-600/20',

  PENDING: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  PENDING_REVIEW: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  PENDING_SCAN: 'bg-amber-50 text-amber-700 ring-amber-600/20',

  REJECTED: 'bg-red-50 text-red-700 ring-red-600/20',
  QUARANTINED: 'bg-red-50 text-red-700 ring-red-600/20',

  INACTIVE: 'bg-slate-100 text-slate-600 ring-slate-500/20',
  ARCHIVED: 'bg-slate-100 text-slate-600 ring-slate-500/20',
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const normalizedStatus = status.trim().toUpperCase()

  const style =
    statusStyles[normalizedStatus] ??
    'bg-blue-50 text-blue-700 ring-blue-600/20'

  const label = normalizedStatus.replaceAll('_', ' ')

  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${style}`}
    >
      {label}
    </span>
  )
}
