import type { ComplianceMetrics } from '../../../api/dashboardService'
import StatCard from '../../../components/ui/StatCard'

interface ComplianceOverviewProps {
  data: ComplianceMetrics
}

function ComplianceProgress({
  label,
  percentage,
  description,
}: {
  label: string
  percentage: number
  description: string
}) {
  const safePercentage = Math.min(100, Math.max(0, percentage))

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-800">{label}</h3>
        <span className="text-lg font-bold tabular-nums text-slate-900">
          {safePercentage.toFixed(1)}%
        </span>
      </div>

      <div
        className="mt-4 h-3 overflow-hidden rounded-full bg-slate-100"
        role="progressbar"
        aria-label={label}
        aria-valuenow={safePercentage}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full rounded-full bg-blue-600 transition-all"
          style={{ width: `${safePercentage}%` }}
        />
      </div>

      <p className="mt-3 text-xs text-slate-500">{description}</p>
    </article>
  )
}

export default function ComplianceOverview({
  data,
}: ComplianceOverviewProps) {
  return (
    <section aria-labelledby="compliance-heading" className="space-y-5">
      <div>
        <h2
          id="compliance-heading"
          className="text-lg font-semibold tracking-tight text-slate-900"
        >
          Compliance overview
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Employee profile and document compliance indicators.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Incomplete Profiles"
          value={data.profiles.incomplete}
          description="Employee profiles requiring completion"
          icon="👤"
        />
        <StatCard
          label="Missing Documents"
          value={data.documents.employees_missing_required_documents}
          description="Employees missing required documents"
          icon="📋"
        />
        <StatCard
          label="Expired Documents"
          value={data.documents.expired_count}
          description="Documents that have expired"
          icon="⚠️"
        />
        <StatCard
          label="Expiring Soon"
          value={data.documents.expiring_soon_count}
          description="Documents approaching expiration"
          icon="⏳"
        />
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <ComplianceProgress
          label="Profile completion"
          percentage={data.profiles.completion_rate}
          description={`${data.profiles.complete} of ${data.headcount} employee profiles complete.`}
        />

        <ComplianceProgress
          label="Document compliance"
          percentage={data.documents.compliance_rate}
          description={`${data.documents.compliant_employees} employees compliant with required documents.`}
        />
      </div>
      <article
        aria-labelledby="expired-documents-heading"
        className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <h3
          id="expired-documents-heading"
          className="text-sm font-semibold text-slate-800"
        >
          Expired document details
        </h3>

        {data.documents.expired_details.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">
            No expired documents.
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-slate-100">
            {data.documents.expired_details.map((document) => (
              <li
                key={document.id}
                className="flex flex-col justify-between gap-2 py-3 sm:flex-row sm:items-center"
              >
                <div>
                  <p className="text-sm font-medium text-slate-900">
                    {document.employee__user__name}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {document.document_type}
                  </p>
                </div>

                <p className="text-sm text-slate-600">
                  <span className="mr-1 text-slate-500">Expired:</span>
                  <time dateTime={document.expires_at}>
                    {document.expires_at}
                  </time>
                </p>
              </li>
            ))}
          </ul>
        )}
      </article>
    </section>
  )
}
